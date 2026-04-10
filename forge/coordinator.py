import asyncio
import logging

from forge.handlers import HandlerRegistry
from forge.models import TaskStatus
from forge.state import transition
from forge.store import TaskStore

logger = logging.getLogger(__name__)


class Coordinator:
    def __init__(self, store: TaskStore, registry: HandlerRegistry, max_concurrent: int = 2, poller=None):
        self._store = store
        self._registry = registry
        self._max_concurrent = max_concurrent
        self._poller = poller

    async def startup(self):
        """Called once on application start. Resets stuck tasks."""
        reset_count = await self._store.reset_active_tasks()
        if reset_count > 0:
            logger.info(f"Reset {reset_count} stuck tasks to queued on startup")

    async def tick(self) -> int:
        """Run one cycle: poll Linear if configured, dequeue pending tasks, process them, return count processed."""
        if self._poller:
            try:
                created = await self._poller.poll()
                if created > 0:
                    logger.info(f"Ingested {created} tasks from Linear")
            except Exception:
                logger.exception("Error polling Linear")
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
                current_status = TaskStatus.QUEUED

                new_status = transition(current_status, TaskStatus.TRIAGING)
                await self._store.update_status(task.id, new_status)
                current_status = new_status

                can_handle = await handler.triage(task)
                if not can_handle:
                    await self._store.mark_failed(task.id, error="Handler declined task during triage")
                    tasks_processed += 1
                    continue

                new_status = transition(current_status, TaskStatus.EXECUTING)
                await self._store.update_status(task.id, new_status)
                current_status = new_status

                result = await handler.execute(task)

                # Persist execute results so verify/deliver can access them
                await self._store.update_handler_data(task.id, result)
                # Reload task with updated handler_data
                task = await self._store.get(task.id)

                new_status = transition(current_status, TaskStatus.VERIFYING)
                await self._store.update_status(task.id, new_status)
                current_status = new_status

                verified = await handler.verify(task)
                if not verified:
                    await self._store.mark_failed(task.id, error="Verification failed")
                    tasks_processed += 1
                    continue

                new_status = transition(current_status, TaskStatus.DELIVERING)
                await self._store.update_status(task.id, new_status)
                current_status = new_status

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
