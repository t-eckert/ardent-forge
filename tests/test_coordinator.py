import asyncio

import pytest

from forge.coordinator import Coordinator
from forge.db import Database
from forge.agents import AgentRegistry
from forge.agents.echo import EchoAgent
from forge.models import Task, TaskSource, TaskStatus, TaskType
from forge.store import TaskStore


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
def store(db):
    return TaskStore(db)


@pytest.fixture
def registry():
    reg = AgentRegistry()
    reg.register(EchoAgent())
    return reg


@pytest.fixture
def coordinator(store, registry):
    return Coordinator(store=store, registry=registry, max_concurrent=2)


async def test_process_single_task(coordinator, store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Process me",
        description="Test processing",
    )
    # Echo handler is registered for "echo" type, not "code"
    # So let's make an echo-typed task
    task.type = TaskType.CODE  # Will not find handler
    await store.save(task)

    # No handler for "code" yet — task should fail
    await coordinator.process_pending()
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.FAILED


async def test_process_echo_task(coordinator, store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Echo me",
        description="Test echo",
    )
    # Override type to match echo handler
    task = task.model_copy(update={"type": "echo"})
    await store.save(task)

    await coordinator.process_pending()
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.COMPLETED
    assert loaded.result is not None


async def test_respects_max_concurrent(coordinator, store):
    tasks = []
    for i in range(5):
        task = Task.new(
            task_type=TaskType.CODE,
            source=TaskSource.CHAT,
            title=f"Task {i}",
            description=f"Concurrent {i}",
        )
        task = task.model_copy(update={"type": "echo"})
        await store.save(task)
        tasks.append(task)

    await coordinator.process_pending()

    completed = await store.list_by_status(TaskStatus.COMPLETED)
    # Should process up to max_concurrent (2) per cycle
    assert len(completed) == 2


async def test_coordinator_tick_processes_and_returns(coordinator, store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Tick test",
        description="Test tick",
    )
    task = task.model_copy(update={"type": "echo"})
    await store.save(task)

    processed = await coordinator.tick()
    assert processed == 1


async def test_coordinator_calls_extra_watchers_in_tick():
    from unittest.mock import AsyncMock

    class FakeStore:
        async def list_pending(self, limit):
            return []

        async def reset_active_tasks(self):
            return 0

        async def list_active_tasks(self):
            return []

        async def list_by_status(self, status):
            return []

        async def list_due_schedules(self, now):
            return []

    store = FakeStore()
    registry = AgentRegistry()
    w1 = AsyncMock()
    w1.poll = AsyncMock(return_value=2)
    w2 = AsyncMock()
    w2.poll = AsyncMock(return_value=0)

    coord = Coordinator(store=store, registry=registry, watchers=[w1, w2])
    await coord.tick()
    w1.poll.assert_awaited_once()
    w2.poll.assert_awaited_once()


from unittest.mock import patch


class BoomAgent:
    name = "boom"
    task_type = "boom"
    stages = ["execute"]
    connectors: list[str] = []
    timeout_seconds = 60

    async def execute(self, task, ctx):
        raise RuntimeError("kaboom")


class SlowAgent:
    name = "slow"
    task_type = "slow"
    stages = ["execute"]
    connectors: list[str] = []
    timeout_seconds = 60

    async def execute(self, task, ctx):
        await asyncio.sleep(5)
        return {}


async def _save(store, type_):
    t = Task.new(task_type=TaskType.ECHO, source=TaskSource.CHAT, title="t", description="d")
    t = t.model_copy(update={"type": type_})
    await store.save(t)
    return t


async def test_transient_exception_requeues_with_backoff(store):
    reg = AgentRegistry()
    reg.register(BoomAgent())
    coord = Coordinator(store=store, registry=reg, max_concurrent=2)

    task = await _save(store, "boom")
    await coord.process_pending()

    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.QUEUED  # requeued, not failed
    assert loaded.retries == 1
    assert loaded.failure_kind == "transient"
    assert loaded.available_at is not None  # backoff gate set


async def test_retries_exhaust_to_terminal_failure(store):
    reg = AgentRegistry()
    reg.register(BoomAgent())
    coord = Coordinator(store=store, registry=reg, max_concurrent=2)

    task = await _save(store, "boom")
    # max_retries default 3 → fails on attempts producing retries 1,2,3 then terminal.
    # Clear the backoff gate before each loop so the task is dequeuable, and stop
    # once it has reached the terminal FAILED state.
    for _ in range(5):
        current = await store.get(task.id)
        if current.status == TaskStatus.FAILED:
            break
        await store._db.execute("UPDATE tasks SET available_at = NULL WHERE id = ?", (task.id,))
        await coord.process_pending()

    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.FAILED
    assert loaded.retries == 3
    assert loaded.failure_kind == "transient"


async def test_timeout_classified_and_requeued(store):
    reg = AgentRegistry()
    reg.register(SlowAgent())
    coord = Coordinator(store=store, registry=reg, max_concurrent=2)

    task = await _save(store, "slow")
    # Per-task override to force a fast timeout.
    await store.update_handler_data(task.id, {"timeout_seconds": 0.05})
    await coord.process_pending()

    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.QUEUED
    assert loaded.failure_kind == "timeout"


async def test_code_task_session_killed_before_retry(store):
    reg = AgentRegistry()
    reg.register(BoomAgent())
    coord = Coordinator(store=store, registry=reg, max_concurrent=2)

    task = await _save(store, "boom")
    await store.update_handler_data(task.id, {"zellij_session": "agent-x"})

    with patch("forge.coordinator.kill_session") as mock_kill:
        await coord.process_pending()
        mock_kill.assert_awaited_once_with("agent-x")


class SessionMidStageAgent:
    """Persists its zellij_session to the store *during* execute (after the task
    was dequeued), then fails — mimics CodeAgent, where the session name isn't in
    the dequeued task object. Exercises that _fail_or_retry re-reads handler_data."""

    name = "midsession"
    task_type = "midsession"
    stages = ["execute"]
    connectors: list[str] = []
    timeout_seconds = 60

    async def execute(self, task, ctx):
        await ctx.store.update_handler_data(task.id, {"zellij_session": "agent-mid"})
        raise RuntimeError("boom after persisting session")


async def test_session_persisted_mid_stage_is_killed_on_failure(store):
    reg = AgentRegistry()
    reg.register(SessionMidStageAgent())
    coord = Coordinator(store=store, registry=reg, max_concurrent=2)

    await _save(store, "midsession")  # dequeued object has no session yet

    with patch("forge.coordinator.kill_session") as mock_kill:
        await coord.process_pending()
        mock_kill.assert_awaited_once_with("agent-mid")


async def test_reaper_requeues_task_past_timeout(store):
    reg = AgentRegistry()
    reg.register(EchoAgent())  # echo timeout_seconds = 60
    coord = Coordinator(store=store, registry=reg, max_concurrent=2)

    task = await _save(store, "echo")
    await store.update_status(task.id, TaskStatus.EXECUTING)
    # Backdate updated_at well past the 60s echo timeout.
    old = "2000-01-01T00:00:00+00:00"
    await store._db.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (old, task.id))

    reaped = await coord.reap_stuck_tasks()
    assert reaped == 1
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.QUEUED
    assert loaded.failure_kind == "timeout"


async def test_reaper_ignores_fresh_active_task(store):
    reg = AgentRegistry()
    reg.register(EchoAgent())
    coord = Coordinator(store=store, registry=reg, max_concurrent=2)

    task = await _save(store, "echo")
    await store.update_status(task.id, TaskStatus.EXECUTING)  # updated_at = now

    reaped = await coord.reap_stuck_tasks()
    assert reaped == 0
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.EXECUTING
