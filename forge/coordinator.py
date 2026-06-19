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
from forge.worktree_reaper import reapable_worktrees
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
        git=None,
    ):
        self._store = store
        self._registry = registry
        self._connectors = connectors
        self._settings = settings
        self._max_concurrent = max_concurrent
        self._poller = poller
        self._watchers = watchers or []
        self._git = git
        ttl_hours = getattr(settings, "worktree_ttl_hours", 48) if settings else 48
        self._worktree_ttl = timedelta(hours=ttl_hours)
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
        """Called once on application start. Reaps tasks left active by an
        unclean shutdown, routing them through the retry/backoff path."""
        reaped = await self.reap_stuck_tasks()
        if reaped > 0:
            logger.info("Reaped %d stuck tasks on startup", reaped)

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

        try:
            reaped = await self.reap_stuck_tasks()
            if reaped > 0:
                logger.info("Reaped %d stuck tasks", reaped)
        except Exception:
            logger.exception("Error reaping stuck tasks")

        try:
            reaped_wt = await self.reap_old_worktrees()
            if reaped_wt > 0:
                logger.info("Reaped %d old worktrees", reaped_wt)
        except Exception:
            logger.exception("Error reaping old worktrees")

        try:
            await self.resume_approved_deliveries()
        except Exception:
            logger.exception("Error resuming approved deliveries")

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
        # Re-load the latest state: a producing stage (e.g. Code) may have
        # persisted ``zellij_session`` to handler_data *after* this task object
        # was dequeued, so the in-hand copy can be stale. Fall back to the passed
        # object if the row has since vanished.
        task = await self._store.get(task.id) or task

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

    async def _deliver_and_complete(self, task: Task, agent, ctx: AgentContext, aggregated: dict) -> None:
        """Run the deliver stage (if any), mark completed, post to Linear.
        Shared by the normal pipeline and the post-approval resume pass."""
        stages = agent.stages
        if "deliver" in stages:
            if task.status != TaskStatus.DELIVERING:
                await self._store.update_status(
                    task.id, transition(task.status, TaskStatus.DELIVERING)
                )
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

        reloaded = await self._store.get(task.id)
        if self._poller is not None and reloaded is not None:
            try:
                await self._poller.post_result(reloaded)
            except Exception:
                logger.exception("Failed to post Linear result for task %s", task.id)

    async def resume_approved_deliveries(self) -> int:
        """Finish tasks approved after an approval-gate pause. Such a task sits
        in `delivering` (set by mark_approved) with its execute/verify results
        already in handler_data; run only its deliver stage + complete. The
        normal pipeline never leaves a task in `delivering` between ticks, so
        this only catches post-approval resumes."""
        # Note: TASK_DURATION_SECONDS is deliberately NOT observed here. A gated
        # task's end-to-end duration would include human approval wait time,
        # which is not comparable to ungated task latency — a metric hole is more
        # honest than a think-time-polluted histogram. TASKS_TOTAL still counts
        # the completion (via _deliver_and_complete).
        resumed = 0
        for task in await self._store.list_by_status(TaskStatus.DELIVERING):
            agent = self._registry.get(task.type)
            if agent is None:
                continue
            ctx = self._build_context(agent)
            aggregated = dict(task.handler_data or {})
            try:
                await self._deliver_and_complete(task, agent, ctx, aggregated)
                resumed += 1
            except TimeoutError as e:
                # Mirror the normal pipeline: deliver is a producing stage and can
                # transiently fail/timeout, so preserve the task's retry budget
                # rather than failing it terminally on the first hiccup.
                logger.warning("Resume-deliver timed out for task %s: %s", task.id, e)
                await self._fail_or_retry(task, error=str(e), kind=retry.TIMEOUT)
                HANDLER_ERRORS_TOTAL.labels(type=task.type).inc()
            except Exception as e:
                logger.exception("Resume-deliver failed for task %s", task.id)
                await self._fail_or_retry(task, error=str(e), kind=retry.TRANSIENT)
                HANDLER_ERRORS_TOTAL.labels(type=task.type).inc()
        return resumed

    async def reap_stuck_tasks(self) -> int:
        """Backstop for tasks orphaned by a crash/restart: any task stuck in an
        active state longer than its effective timeout is routed through the
        same timeout path as an in-process timeout (teardown + retry-or-fail)."""
        now = datetime.now(timezone.utc)
        reaped = 0
        for task in await self._store.list_active_tasks():
            agent = self._registry.get(task.type)
            timeout = (
                self._effective_timeout(task, agent)
                if agent is not None
                else self._default_timeout
            )
            age = (now - task.updated_at).total_seconds()
            if age > timeout:
                await self._fail_or_retry(
                    task,
                    error=f"Task stuck in {task.status} for {int(age)}s "
                    f"(timeout {int(timeout)}s)",
                    kind=retry.TIMEOUT,
                )
                reaped += 1
        return reaped

    async def reap_old_worktrees(self) -> int:
        """Reclaim Code-task git worktrees that are no longer referenced by any
        active task and whose newest reference is older than the TTL. No-ops when
        no git helper is wired (tests)."""
        if self._git is None:
            return 0
        tasks = await self._store.list_tasks_with_worktrees()
        targets = reapable_worktrees(
            tasks, datetime.now(timezone.utc), self._worktree_ttl
        )
        removed = 0
        for repo_path, worktree_path in targets:
            try:
                await self._git.cleanup_worktree(repo_path, worktree_path)
                await self._git.prune_worktrees(repo_path)
                removed += 1
            except Exception:
                logger.warning("Failed to reap worktree %s", worktree_path, exc_info=True)
        return removed

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
                refreshed = await self._store.get(task.id)
                if refreshed is None:
                    logger.error(
                        "Task %s vanished from DB after execute; skipping", task.id
                    )
                    continue
                task = refreshed

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

                # Approval gate — park before deliver if the task opted in.
                if task.require_approval and "deliver" in stages:
                    await self._store.update_status(
                        task.id, transition(current_status, TaskStatus.AWAITING_APPROVAL)
                    )
                    continue
                if task.require_approval and "deliver" not in stages:
                    # The gate only has meaning before a deliver stage; an
                    # execute/verify-only agent has nothing to gate. Don't
                    # silently honor the flag — surface that it was a no-op.
                    logger.warning(
                        "Task %s requested approval but agent %s has no deliver "
                        "stage; completing without a gate",
                        task.id,
                        task.type,
                    )

                await self._deliver_and_complete(task, agent, ctx, aggregated)
                TASK_DURATION_SECONDS.labels(type=task.type).observe(
                    time.monotonic() - task_start
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
