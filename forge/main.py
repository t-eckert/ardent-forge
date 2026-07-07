import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from forge.api import (
    agents as agents_api,
    connectors as connectors_api,
    health,
    memory as memory_api,
    notebook as notebook_api,
    repos as repos_api,
    schedules,
    tasks,
    uploads as uploads_api,
    weather as weather_api,
)
from forge.config import Settings
from forge.connectors import ConnectorRegistry
from forge.coordinator import Coordinator
from forge.db import Database
from forge.git import GitOps
from forge.agents import AgentRegistry
from forge.agents.echo import EchoAgent
from forge.memory import MemoryStore
from forge.repos import RepoRegistry
from forge.store import TaskStore


def create_app(db: Database | None = None, settings: "Settings | None" = None) -> FastAPI:
    app = FastAPI(title="Ardent Forge")

    # MCP server — mounted in-process so its tools call Forge's services
    # directly. Services are injected via mcp.configure() in the lifespan;
    # the session manager is run there too. Conditional tools are decided
    # from settings here at build time.
    from forge.mcp import build_mcp_server

    mcp_server = build_mcp_server(settings or Settings())
    app.state.mcp_server = mcp_server
    app.mount("/mcp", mcp_server.streamable_http_app())

    # Starlette's Mount only matches the prefix *with* a trailing slash, so a
    # request to the bare "/mcp" returns Match.NONE and falls through to the
    # SPA catch-all StaticFiles mount at "/" (added in run()), which 405s any
    # non-GET. Redirect the bare path to "/mcp/" — registered before the SPA
    # mount so it wins, and MCP clients follow the 307 (preserving method/body).
    async def _mcp_trailing_slash(request: Request) -> RedirectResponse:
        target = "/mcp/"
        if request.url.query:
            target += "?" + request.url.query
        return RedirectResponse(url=target, status_code=307)

    app.add_route("/mcp", _mcp_trailing_slash, methods=["GET", "POST", "DELETE"])

    app.include_router(health.router)
    app.include_router(tasks.router)
    app.include_router(schedules.router)
    app.include_router(connectors_api.router)
    app.include_router(memory_api.router)
    app.include_router(agents_api.router)
    app.include_router(notebook_api.router)
    app.include_router(repos_api.router)
    app.include_router(weather_api.router)
    app.include_router(uploads_api.router)

    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    if db is not None:
        store = TaskStore(db)
        tasks.set_store(store)
        schedules.set_store(store)

    return app


async def _upload_cleanup_loop(service) -> None:
    while True:
        n = service.delete_old_files(max_age_days=7)
        if n:
            logging.getLogger(__name__).info("Cleaned up %d old upload(s)", n)
        await asyncio.sleep(86400)


def run():
    settings = Settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """
        This is where the whole system is assembled.
        """

        # Initialize a connection to the database.
        db = Database(settings.db_path)
        await db.initialize()

        from pathlib import Path
        from forge.uploads import UploadService

        upload_service = UploadService(Path(settings.upload_dir).expanduser())
        upload_service.ensure_dir()
        uploads_api.set_service(upload_service)
        upload_cleanup_task = asyncio.create_task(_upload_cleanup_loop(upload_service))

        # Initialize the task store.
        store = TaskStore(db)

        repo_registry = RepoRegistry(settings.workspace_dir, projects_dir=settings.projects_dir)
        await repo_registry.scan()
        await repo_registry.scan_projects()
        repos_api.set_registry(repo_registry)
        app.state.repo_registry = repo_registry

        from forge.notebook import NotebookReader, NotebookWriter

        notebook_reader: NotebookReader | None = None
        notebook_writer: NotebookWriter | None = None
        notebook_path = Path(settings.notebook_dir)
        if notebook_path.is_dir():
            try:
                notebook_reader = NotebookReader(notebook_path)
                notebook_writer = NotebookWriter(notebook_path)
            except Exception as e:
                import logging

                logging.getLogger(__name__).warning(f"Notebook disabled: {e}")
        else:
            import logging

            logging.getLogger(__name__).warning(
                f"Notebook directory {notebook_path} not found; notebook features disabled"
            )
        app.state.notebook_reader = notebook_reader
        app.state.notebook_writer = notebook_writer

        # Connectors
        connectors = ConnectorRegistry()
        from forge.connectors.onepassword import OPConnector
        from forge.connectors.weather import WeatherConnector

        connectors.register(OPConnector())
        connectors.register(WeatherConnector())
        if settings.tavily_api_key:
            from forge.connectors.web_search import WebSearchConnector

            connectors.register(WebSearchConnector(api_key=settings.tavily_api_key))
        if notebook_path.is_dir():
            from forge.connectors.notebook import NotebookConnector

            connectors.register(NotebookConnector(notebook_path, tz=settings.timezone))

        # Speed test — periodic bandwidth measurement.
        from forge.connectors.speedtest import SpeedtestConnector

        speedtest_connector = SpeedtestConnector(
            db=db, interval_minutes=settings.speedtest_interval_minutes
        )
        connectors.register(speedtest_connector)
        await connectors.setup_all()

        tasks.set_store(store)
        schedules.set_store(store)

        app.state.connectors = connectors

        registry = AgentRegistry()
        registry.register(EchoAgent())
        from forge.agents.code import CodeAgent

        registry.register(
            CodeAgent(
                workspace_dir=settings.workspace_dir,
            )
        )

        # Self-building: plan agent (always registered)
        from forge.agents.plan import PlanAgent

        registry.register(
            PlanAgent(
                workspace_dir=settings.workspace_dir,
                self_repo=settings.self_repo,
                claude_model=settings.planner_claude_model,
            )
        )

        app.state.agent_registry = registry

        poller = None
        if settings.linear_api_key and settings.linear_team_id:
            from forge.linear.client import LinearClient
            from forge.linear.poller import LinearPoller

            linear_client = LinearClient(api_key=settings.linear_api_key)
            poller = LinearPoller(
                client=linear_client,
                store=store,
                team_id=settings.linear_team_id,
            )

            from forge.agents.tickets import TicketsAgent
            from forge.linear.projects import LinearProjectsAPI

            tickets_linear = LinearProjectsAPI(linear_client)
            registry.register(
                TicketsAgent(
                    workspace_dir=settings.workspace_dir,
                    linear=tickets_linear,
                    team_id=settings.linear_team_id,
                    self_repo=settings.self_repo,
                )
            )

        # Self-building watchers
        from forge.watchers.spec_watcher import SpecWatcher

        watchers: list = [speedtest_connector]
        try:
            af_repo_path = await GitOps(settings.workspace_dir).ensure_repo(
                settings.self_repo_url, settings.self_repo
            )

            async def _fetch_main() -> None:
                git = GitOps(settings.workspace_dir)
                await git._run(["git", "fetch", "origin", "main"], cwd=af_repo_path)
                await git._run(["git", "checkout", "main"], cwd=af_repo_path)
                await git._run(["git", "reset", "--hard", "origin/main"], cwd=af_repo_path)

            watchers.append(
                SpecWatcher(
                    store=store,
                    repo_path=af_repo_path,
                    fetch_fn=_fetch_main,
                    self_repo=settings.self_repo,
                )
            )
        except Exception:
            import logging as _logging

            _logging.getLogger(__name__).exception(
                "self-building watchers disabled: could not clone AF repo"
            )

        memory_store = MemoryStore(settings.memory_dir)
        app.state.memory_store = memory_store

        # Pre-register Prometheus series for every known label combination so
        # Grafana panels show 0 instead of "No data" on a freshly-booted forge.
        from forge.metrics import prime_metrics

        prime_metrics(registry, connectors)

        coordinator = Coordinator(
            store=store,
            registry=registry,
            connectors=connectors,
            settings=settings,
            max_concurrent=settings.max_concurrent_tasks,
            poller=poller,
            watchers=watchers,
            git=GitOps(settings.workspace_dir),
        )
        app.state.coordinator = coordinator
        tasks.set_coordinator(coordinator)

        # Wire the MCP server's tools to the live services.
        from forge.mcp import configure as mcp_configure

        mcp_configure(
            store=store,
            memory=memory_store,
            repo_registry=repo_registry,
            coordinator=coordinator,
            connectors=connectors,
            notebook_reader=notebook_reader,
        )

        await coordinator.startup()

        loop_task = asyncio.create_task(
            coordinator.run_loop(poll_interval=settings.poll_interval_seconds)
        )

        async with app.state.mcp_server.session_manager.run():
            yield

        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass
        upload_cleanup_task.cancel()
        try:
            await upload_cleanup_task
        except asyncio.CancelledError:
            pass
        await db.close()

    app = create_app(settings=settings)
    app.router.lifespan_context = lifespan

    ui_build_dir = os.path.join(os.path.dirname(__file__), "..", "ui", "build")
    if os.path.isdir(ui_build_dir):
        # SPA fallback: the SvelteKit static adapter builds with
        # `fallback: "index.html"`, producing a single index.html that the
        # client-side router rehydrates for every route. Plain StaticFiles
        # 404s on /today, /threads/xyz, etc. — this subclass falls back to
        # index.html for any request that isn't a real file, so page
        # reloads on deep routes work.
        class SPAStaticFiles(StaticFiles):
            async def get_response(self, path, scope):
                try:
                    return await super().get_response(path, scope)
                except StarletteHTTPException as exc:
                    if exc.status_code == 404:
                        return await super().get_response("index.html", scope)
                    raise

        app.mount("/", SPAStaticFiles(directory=ui_build_dir, html=True), name="ui")

    uvicorn.run(app, host=settings.host, port=settings.port)
