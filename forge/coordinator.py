import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from forge.agents import AgentContext, AgentRegistry
from forge.connectors import ConnectorRegistry
from forge.metrics import (
    ACTIVE_TASKS,
    CONNECTOR_HEALTH,
    HANDLER_ERRORS_TOTAL,
    LINEAR_POLLS_TOTAL,
    LINEAR_TASKS_INGESTED,
    QUEUE_DEPTH,
    TASK_DURATION_SECONDS,
    TASK_STAGE_DURATION_SECONDS,
    TASKS_TOTAL,
    TICK_DURATION_SECONDS,
    TICKS_TOTAL,
)
from forge.models import Task, TaskSource, TaskStatus, TaskType
from forge.state import transition
from forge.store import TaskStore
from forge import retry
from forge.zellij import kill_session

logger = logging.getLogger(__name__)


class Coordinator:
    def __init__(
        self,
        store: TaskStore,
        registry: AgentRegistry,
        connectors: ConnectorRegistry | None = None,
        settings=None,
        max_concurrent: int = 2,
        poller=None,
        watchers: list | None = None,
        orchestrator=None,
    ):
        self._store = store
        self._registry = registry
        self._connectors = connectors
        self._settings = settings
        self._max_concurrent = max_concurrent
        self._poller = poller
        self._watchers = watchers or []
        self._orchestrator = orchestrator
        # Resilience config — read from settings with safe fallbacks for tests
        # that construct the coordinator without a Settings object.
        self._max_retries = getattr(settings, "max_retries", 3) if settings else 3
        self._retry_base = getattr(settings, "retry_base_seconds", 60) if settings else 60
        self._retry_cap = getattr(settings, "retry_max_seconds", 900) if settings else 900
        self._default_timeout = (
            getattr(settings, "default_timeout_seconds", 1800) if settings else 1800
        )
        # Wake signal — chat.py sets this after dispatching a task so the
        # coordinator starts processing within seconds instead of waiting for
        # the next poll tick. Created lazily on first loop entry so it binds
        # to the running event loop.
        self._wake: asyncio.Event | None = None

    def nudge(self) -> None:
        """Ask the coordinator to run a tick as soon as possible.

        Safe to call from any coroutine, synchronous with respect to the loop
        via the underlying ``asyncio.Event``. A no-op if ``run_loop`` hasn't
        started yet (e.g. in unit tests) — ticks will happen on their own
        schedule when the loop eventually starts.
        """
        if self._wake is not None:
            self._wake.set()

    async def startup(self):
        """Called once on application start. Resets stuck tasks."""
        reset_count = await self._store.reset_active_tasks()
        if reset_count > 0:
            logger.info(f"Reset {reset_count} stuck tasks to queued on startup")

    async def tick(self) -> int:
        """Run one cycle: poll Linear if configured, dequeue pending tasks, process them."""
        tick_start = time.monotonic()
        TICKS_TOTAL.inc()

        if self._connectors is not None:
            try:
                health = await self._connectors.health_check()
                for name, ok in health.items():
                    CONNECTOR_HEALTH.labels(connector=name).set(1 if ok else 0)
            except Exception:
                logger.exception("Connector health check failed")

        if self._poller:
            try:
                created = await self._poller.poll()
                LINEAR_POLLS_TOTAL.labels(result="success").inc()
                if created > 0:
                    LINEAR_TASKS_INGESTED.inc(created)
                    logger.info(f"Ingested {created} tasks from Linear")
            except Exception:
                LINEAR_POLLS_TOTAL.labels(result="error").inc()
                logger.exception("Error polling Linear")

        for watcher in self._watchers:
            try:
                n = await watcher.poll()
                if n > 0:
                    logger.info(f"Watcher {watcher.__class__.__name__} enqueued {n} tasks")
            except Exception:
                logger.exception(f"Error in watcher {watcher.__class__.__name__}")

        try:
            fired = await self._fire_due_schedules()
            if fired > 0:
                logger.info("Fired %d scheduled tasks", fired)
        except Exception:
            logger.exception("Error firing schedules")

        result = await self.process_pending()
        TICK_DURATION_SECONDS.observe(time.monotonic() - tick_start)
        return result

    async def _fire_due_schedules(self) -> int:
        """Create tasks for any enabled schedules whose next_run has passed."""
        import json as _json
        from datetime import datetime, timezone
        from croniter import croniter

        now = datetime.now(timezone.utc)
        due = await self._store.list_due_schedules(now.isoformat())
        fired = 0
        for sched in due:
            template = _json.loads(sched.get("task_template") or "{}")
            try:
                task_type = TaskType(sched["task_type"])
            except ValueError:
                logger.warning("Unknown task_type in schedule %r: %r", sched["id"], sched["task_type"])
                continue
            task = Task.new(
                task_type=task_type,
                source=TaskSource.SCHEDULE,
                title=template.get("title") or sched["name"],
                description=template.get("description") or sched["name"],
                repo=template.get("repo"),
            )
            await self._store.save(task)
            next_run = croniter(sched["cron_expr"], now).get_next(datetime).isoformat()
            await self._store.update_schedule_after_run(sched["id"], now.isoformat(), next_run)
            logger.info("Schedule %r fired task %s (next: %s)", sched["name"], task.id, next_run)
            fired += 1
        return fired

    def _build_context(self, agent) -> AgentContext:
        tools = []
        if self._connectors is not None and agent.connectors:
            tools = self._connectors.tools_for(agent.connectors)
        return AgentContext(tools=tools, store=self._store, settings=self._settings)

    def _effective_timeout(self, task: Task, agent) -> float:
        """Resolve the timeout for a producing stage: per-task override →
        agent default → global default."""
        override = (task.handler_data or {}).get("timeout_seconds")
        if override:
            return float(override)
        return float(getattr(agent, "timeout_seconds", None) or self._default_timeout)

    async def _fail_or_retry(self, task: Task, error: str, kind: str) -> None:
        """Single funnel for every failure. Tears down any orphaned Zellij
        session, then requeues with backoff (retryable + budget left) or marks
        the task terminally failed."""
        session = (task.handler_data or {}).get("zellij_session")
        if session:
            try:
                await kill_session(session)
            except Exception:
                logger.exception("kill_session failed for %s", session)

        if retry.is_retryable(kind) and task.retries < self._max_retries:
            next_attempt = task.retries + 1
            delay = retry.backoff(next_attempt, self._retry_base, self._retry_cap)
            available_at = (
                datetime.now(timezone.utc) + timedelta(seconds=delay)
            ).isoformat()
            await self._store.requeue(
                task.id,
                retries=next_attempt,
                available_at=available_at,
                error=error,
                kind=kind,
            )
            logger.info(
                "Requeued task %s (attempt %d/%d, kind=%s, backoff=%ss)",
                task.id, next_attempt, self._max_retries, kind, delay,
            )
        else:
            await self._store.mark_failed(task.id, error=error, kind=kind)
            TASKS_TOTAL.labels(type=task.type, status="failed").inc()

    async def process_pending(self) -> int:
        pending = await self._store.list_pending(limit=self._max_concurrent)
        QUEUE_DEPTH.set(len(pending))
        if not pending:
            return 0

        tasks_processed = 0
        for task in pending:
            agent = self._registry.get(task.type)
            if agent is None:
                logger.warning(
                    f"No agent for task type '{task.type}', failing task {task.id}"
                )
                await self._fail_or_retry(
                    task,
                    error=f"No agent registered for type '{task.type}'",
                    kind=retry.TERMINAL,
                )
                tasks_processed += 1
                continue

            task_start = time.monotonic()
            ACTIVE_TASKS.inc()
            try:
                tasks_processed += 1
                ctx = self._build_context(agent)
                current_status = TaskStatus.QUEUED
                stages = agent.stages
                aggregated: dict = {}

                # Triage — optional.
                if "triage" in stages:
                    new_status = transition(current_status, TaskStatus.TRIAGING)
                    await self._store.update_status(task.id, new_status)
                    current_status = new_status

                    stage_start = time.monotonic()
                    ok = await agent.triage(task, ctx)
                    TASK_STAGE_DURATION_SECONDS.labels(stage="triage").observe(
                        time.monotonic() - stage_start
                    )
                    if not ok:
                        # A gate may leave an actionable reason on handler_data
                        # (see Agent protocol docstring); surface it instead of
                        # the opaque generic message when present.
                        reloaded = await self._store.get(task.id)
                        reason = None
                        if reloaded is not None:
                            reason = (reloaded.handler_data or {}).get("triage_reason")
                        await self._fail_or_retry(
                            task,
                            error=reason or "Agent declined task during triage",
                            kind=retry.DECLINED,
                        )
                        continue

                # Execute — always present per AgentRegistry validation.
                new_status = transition(current_status, TaskStatus.EXECUTING)
                await self._store.update_status(task.id, new_status)
                current_status = new_status

                stage_start = time.monotonic()
                result = await asyncio.wait_for(
                    agent.execute(task, ctx),
                    timeout=self._effective_timeout(task, agent),
                )
                TASK_STAGE_DURATION_SECONDS.labels(stage="execute").observe(
                    time.monotonic() - stage_start
                )
                aggregated = dict(result or {})
                await self._store.update_handler_data(task.id, aggregated)
                task = await self._store.get(task.id)

                # Verify — optional.
                if "verify" in stages:
                    new_status = transition(current_status, TaskStatus.VERIFYING)
                    await self._store.update_status(task.id, new_status)
                    current_status = new_status

                    stage_start = time.monotonic()
                    verified = await agent.verify(task, ctx)
                    TASK_STAGE_DURATION_SECONDS.labels(stage="verify").observe(
                        time.monotonic() - stage_start
                    )
                    if not verified:
                        await self._fail_or_retry(
                            task, error="Verification failed", kind=retry.VERIFICATION
                        )
                        continue

                # Deliver — optional.
                if "deliver" in stages:
                    new_status = transition(current_status, TaskStatus.DELIVERING)
                    await self._store.update_status(task.id, new_status)
                    current_status = new_status

                    stage_start = time.monotonic()
                    delivery = await asyncio.wait_for(
                        agent.deliver(task, ctx),
                        timeout=self._effective_timeout(task, agent),
                    )
                    TASK_STAGE_DURATION_SECONDS.labels(stage="deliver").observe(
                        time.monotonic() - stage_start
                    )
                    aggregated = {**aggregated, **(delivery or {})}

                await self._store.mark_completed(task.id, aggregated)
                TASKS_TOTAL.labels(type=task.type, status="completed").inc()
                TASK_DURATION_SECONDS.labels(type=task.type).observe(
                    time.monotonic() - task_start
                )

                # Post-back resolution to the origin thread, if any. Thread-born
                # tasks get narrated by Forge in the same thread; cron/watcher
                # tasks stay silent and reveal themselves via state.
                reloaded = await self._store.get(task.id)
                if self._orchestrator is not None and reloaded is not None:
                    try:
                        await self._orchestrator.post_resolution(
                            task=reloaded, result=aggregated
                        )
                    except Exception:
                        logger.exception(
                            "Failed to post resolution for task %s", task.id
                        )

                # Post PR link back to Linear for LINEAR-sourced tasks.
                if self._poller is not None and reloaded is not None:
                    try:
                        await self._poller.post_result(reloaded)
                    except Exception:
                        logger.exception(
                            "Failed to post Linear result for task %s", task.id
                        )

            except TimeoutError as e:
                logger.warning("Task %s timed out: %s", task.id, e)
                await self._fail_or_retry(task, error=str(e), kind=retry.TIMEOUT)
                HANDLER_ERRORS_TOTAL.labels(type=task.type).inc()
            except Exception as e:
                logger.exception(f"Error processing task {task.id}")
                await self._fail_or_retry(task, error=str(e), kind=retry.TRANSIENT)
                HANDLER_ERRORS_TOTAL.labels(type=task.type).inc()
            finally:
                ACTIVE_TASKS.dec()

        return tasks_processed

    async def run_loop(self, poll_interval: float = 300):
        """Run the coordinator loop indefinitely. Used by the FastAPI lifespan.

        Each iteration runs one tick, then waits up to ``poll_interval`` seconds
        before the next — but will wake immediately if ``nudge()`` is called.
        This keeps external pollers (Linear, watchers) on their slow cadence
        while making chat-dispatched tasks feel interactive.
        """
        self._wake = asyncio.Event()
        logger.info(f"Coordinator loop started (interval={poll_interval}s)")
        while True:
            try:
                processed = await self.tick()
                if processed > 0:
                    logger.info(f"Processed {processed} tasks")
            except Exception:
                logger.exception("Error in coordinator loop")
            # Wait for either the timeout or a nudge, whichever comes first.
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=poll_interval)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()
