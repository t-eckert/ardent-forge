import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from forge.api import health, tasks
from forge.config import Settings
from forge.coordinator import Coordinator
from forge.db import Database
from forge.handlers import HandlerRegistry
from forge.handlers.echo import EchoHandler
from forge.store import TaskStore


def create_app(db: Database | None = None) -> FastAPI:
    app = FastAPI(title="Ardent Forge")
    app.include_router(health.router)
    app.include_router(tasks.router)

    if db is not None:
        store = TaskStore(db)
        tasks.set_store(store)

    return app


def run():
    settings = Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.db_path)
        await db.initialize()

        store = TaskStore(db)
        tasks.set_store(store)

        registry = HandlerRegistry()
        registry.register(EchoHandler())

        coordinator = Coordinator(
            store=store,
            registry=registry,
            max_concurrent=settings.max_concurrent_tasks,
        )

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
    uvicorn.run(app, host=settings.host, port=settings.port)
