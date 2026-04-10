import asyncio
import logging

from forge.handlers import HandlerRegistry
from forge.models import TaskStatus
from forge.store import TaskStore

logger = logging.getLogger(__name__)


class Coordinator:
    def __init__(self, store: TaskStore, registry: HandlerRegistry, max_concurrent: int = 2):
        self._store = store
        self._registry = registry
        self._max_concurrent = max_concurrent

    async def startup(self):
        """Called once on application start. Resets stuck tasks."""
        reset_count = await self._store.reset_active_tasks()
        if reset_count > 0:
            logger.info(f"Reset {reset_count} stuck tasks to queued on startup")

    async def tick(self) -> int:
        """Run one cycle: dequeue pending tasks, process them, return count processed."""
        return await self.process_pending()

    async def process_pending(self) -> int:
        pending = await self._store.list_pending(limit=self._max_concurrent)
        if not pending:
            return 0

        tasks_processed = 0
        for task in pending:
            handler = self._registry.get(task.type)
            if handler is None:
                logger.warning(f"No handler for task type '{task.type}', failing task {task.id}")
                await self._store.mark_failed(task.id, error=f"No handler registered for type '{task.type}'")
                tasks_processed += 1
                continue

            try:
                await self._store.update_status(task.id, TaskStatus.TRIAGING)
                can_handle = await handler.triage(task)
                if not can_handle:
                    await self._store.mark_failed(task.id, error="Handler declined task during triage")
                    tasks_processed += 1
                    continue

                await self._store.update_status(task.id, TaskStatus.EXECUTING)
                result = await handler.execute(task)

                await self._store.update_status(task.id, TaskStatus.VERIFYING)
                verified = await handler.verify(task)
                if not verified:
                    await self._store.mark_failed(task.id, error="Verification failed")
                    tasks_processed += 1
                    continue

                await self._store.update_status(task.id, TaskStatus.DELIVERING)
                delivery = await handler.deliver(task)

                final_result = {**result, **delivery}
                await self._store.mark_completed(task.id, final_result)
                tasks_processed += 1

            except Exception as e:
                logger.exception(f"Error processing task {task.id}")
                await self._store.mark_failed(task.id, error=str(e))
                tasks_processed += 1

        return tasks_processed

    async def run_loop(self, poll_interval: float = 300):
        """Run the coordinator loop indefinitely. Used by the FastAPI lifespan."""
        logger.info(f"Coordinator loop started (interval={poll_interval}s)")
        while True:
            try:
                processed = await self.tick()
                if processed > 0:
                    logger.info(f"Processed {processed} tasks")
            except Exception:
                logger.exception("Error in coordinator loop")
            await asyncio.sleep(poll_interval)
