import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from forge.api import (
    agents as agents_api,
    chat,
    connectors as connectors_api,
    fields as fields_api,
    health,
    memory as memory_api,
    notebook as notebook_api,
    schedules,
    tasks,
    threads as threads_api,
    todos as todos_api,
    weather as weather_api,
)
from forge.config import Settings
from forge.connectors import ConnectorRegistry
from forge.connectors.weather import WeatherConnector
from forge.coordinator import Coordinator
from forge.db import Database
from forge.agents import AgentRegistry
from forge.agents.echo import EchoAgent
from forge.memory import MemoryStore
from forge.orchestrator import ForgeOrchestrator
from forge.store import TaskStore
from forge.thread_store import ThreadStore


def create_app(db: Database | None = None) -> FastAPI:
    app = FastAPI(title="Ardent Forge")
    app.include_router(health.router)
    app.include_router(tasks.router)
    app.include_router(chat.router)
    app.include_router(schedules.router)
    app.include_router(connectors_api.router)
    app.include_router(memory_api.router)
    app.include_router(threads_api.router)
    app.include_router(agents_api.router)
    app.include_router(fields_api.router)
    app.include_router(notebook_api.router)
    app.include_router(weather_api.router)
    app.include_router(todos_api.router)

    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    if db is not None:
        store = TaskStore(db)
        tasks.set_store(store)
        chat.configure(store=store)
        schedules.set_store(store)

    return app


def run():
    settings = Settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.db_path)
        await db.initialize()

        store = TaskStore(db)
        from pathlib import Path

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

                logging.getLogger(__name__).warning(
                    f"Notebook disabled: {e}"
                )
        else:
            import logging

            logging.getLogger(__name__).warning(
                f"Notebook directory {notebook_path} not found; notebook features disabled"
            )
        app.state.notebook_reader = notebook_reader
        app.state.notebook_writer = notebook_writer
        # Connectors — registered before chat so tools are available on first turn.
        connectors = ConnectorRegistry()
        connectors.register(WeatherConnector())
        if settings.tavily_api_key:
            from forge.connectors.web_search import WebSearchConnector

            connectors.register(WebSearchConnector(api_key=settings.tavily_api_key))
        if notebook_path.is_dir():
            from forge.connectors.notebook import NotebookConnector

            connectors.register(NotebookConnector(notebook_path))
        # Workouts — wraps the notebook logs and Strava. Registers even when
        # Strava creds are missing (notebook-only mode), as long as the
        # vault is available.
        if notebook_path.is_dir():
            from forge.connectors.workout import WorkoutConnector

            connectors.register(
                WorkoutConnector(
                    notebook_root=notebook_path,
                    strava_client_id=settings.strava_client_id,
                    strava_client_secret=settings.strava_client_secret,
                    strava_refresh_token=settings.strava_refresh_token,
                    strava_token_path=Path(settings.strava_token_path),
                )
            )
        await connectors.setup_all()

        tasks.set_store(store)
        chat.configure(
            store=store,
            connectors=connectors,
            anthropic_api_key=settings.anthropic_api_key,
        )
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

        if notebook_reader is not None:
            from forge.agents.research import ResearchAgent
            from forge.claude import ClaudeRunner

            registry.register(
                ResearchAgent(
                    claude_runner=ClaudeRunner(
                        model="claude-sonnet-4-20250514",
                        timeout=600,
                    ),
                    notebook_root=Path(settings.notebook_dir),
                )
            )

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
        from forge.git import GitOps
        from forge.watchers.spec_watcher import SpecWatcher
        from forge.watchers.plan_merge_watcher import PlanMergeWatcher

        watchers: list = []
        try:
            af_repo_path = await GitOps(settings.workspace_dir).ensure_repo(
                settings.self_repo_url, settings.self_repo
            )

            async def _fetch_main() -> None:
                git = GitOps(settings.workspace_dir)
                await git._run("git fetch origin main", cwd=af_repo_path)
                await git._run("git checkout main", cwd=af_repo_path)
                await git._run("git reset --hard origin/main", cwd=af_repo_path)

            watchers.append(
                SpecWatcher(
                    store=store,
                    repo_path=af_repo_path,
                    fetch_fn=_fetch_main,
                    self_repo=settings.self_repo,
                )
            )
            watchers.append(
                PlanMergeWatcher(
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

        # Orchestrator — needs both registries fully populated.
        thread_store = ThreadStore(db)
        memory_store = MemoryStore(settings.memory_dir)
        orchestrator = ForgeOrchestrator(
            connectors=connectors,
            agents=registry,
            store=store,
            thread_store=thread_store,
            memory=memory_store,
        )
        chat.configure(
            store=store,
            connectors=connectors,
            orchestrator=orchestrator,
            thread_store=thread_store,
            anthropic_api_key=settings.anthropic_api_key,
        )
        app.state.orchestrator = orchestrator
        app.state.thread_store = thread_store
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
            orchestrator=orchestrator,
            max_concurrent=settings.max_concurrent_tasks,
            poller=poller,
            watchers=watchers,
        )
        # Hand the coordinator to chat so dispatched tasks can nudge the loop
        # for near-immediate processing instead of waiting a full tick.
        chat.configure(store=store, coordinator=coordinator)
        app.state.coordinator = coordinator

        await coordinator.startup()

        loop_task = asyncio.create_task(
            coordinator.run_loop(poll_interval=settings.poll_interval_seconds)
        )

        yield

        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass
        await db.close()

    app = create_app()
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
