import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from forge.api import chat, connectors as connectors_api, health, schedules, tasks
from forge.config import Settings
from forge.connectors import ConnectorRegistry
from forge.connectors.weather import WeatherConnector
from forge.coordinator import Coordinator
from forge.db import Database
from forge.handlers import HandlerRegistry
from forge.handlers.echo import EchoHandler
from forge.store import TaskStore


def create_app(db: Database | None = None) -> FastAPI:
    app = FastAPI(title="Ardent Forge")
    app.include_router(health.router)
    app.include_router(tasks.router)
    app.include_router(chat.router)
    app.include_router(schedules.router)
    app.include_router(connectors_api.router)

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
        # Connectors — registered before chat so tools are available on first turn.
        connectors = ConnectorRegistry()
        connectors.register(WeatherConnector())
        await connectors.setup_all()

        tasks.set_store(store)
        chat.configure(
            store=store,
            connectors=connectors,
            anthropic_api_key=settings.anthropic_api_key,
        )
        schedules.set_store(store)

        app.state.connectors = connectors

        registry = HandlerRegistry()
        registry.register(EchoHandler())
        from forge.handlers.code import CodeHandler

        registry.register(
            CodeHandler(
                workspace_dir=settings.workspace_dir,
            )
        )

        # Self-building: plan handler (always registered)
        from forge.handlers.plan import PlanHandler

        registry.register(
            PlanHandler(
                workspace_dir=settings.workspace_dir,
                self_repo=settings.self_repo,
                claude_model=settings.planner_claude_model,
            )
        )

        if notebook_reader is not None:
            from forge.claude import ClaudeRunner
            from forge.handlers.research import ResearchHandler

            registry.register(
                ResearchHandler(
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

            from forge.handlers.tickets import TicketsHandler
            from forge.linear.projects import LinearProjectsAPI

            tickets_linear = LinearProjectsAPI(linear_client)
            registry.register(
                TicketsHandler(
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

        coordinator = Coordinator(
            store=store,
            registry=registry,
            max_concurrent=settings.max_concurrent_tasks,
            poller=poller,
            watchers=watchers,
        )

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
        app.mount("/", StaticFiles(directory=ui_build_dir, html=True), name="ui")

    uvicorn.run(app, host=settings.host, port=settings.port)
