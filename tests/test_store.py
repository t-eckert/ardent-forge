import pytest
from datetime import datetime, timedelta, timezone

from forge.db import Database
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


async def test_save_and_get_task(store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Save me",
        description="Test persistence",
    )
    await store.save(task)
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.id == task.id
    assert loaded.title == "Save me"


async def test_get_nonexistent_returns_none(store):
    result = await store.get("nonexistent-id")
    assert result is None


async def test_update_status(store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Update me",
        description="Test status update",
    )
    await store.save(task)
    await store.update_status(task.id, TaskStatus.EXECUTING)
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.EXECUTING


async def test_list_by_status(store):
    for i in range(3):
        task = Task.new(
            task_type=TaskType.CODE,
            source=TaskSource.CHAT,
            title=f"Task {i}",
            description="Queued task",
        )
        await store.save(task)

    executing_task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Executing",
        description="Running",
    )
    await store.save(executing_task)
    await store.update_status(executing_task.id, TaskStatus.EXECUTING)

    queued = await store.list_by_status(TaskStatus.QUEUED)
    assert len(queued) == 3

    executing = await store.list_by_status(TaskStatus.EXECUTING)
    assert len(executing) == 1


async def test_list_pending_returns_queued_oldest_first(store):
    tasks = []
    for i in range(3):
        task = Task.new(
            task_type=TaskType.CODE,
            source=TaskSource.CHAT,
            title=f"Task {i}",
            description=f"Pending {i}",
        )
        await store.save(task)
        tasks.append(task)

    pending = await store.list_pending(limit=2)
    assert len(pending) == 2
    assert pending[0].title == "Task 0"
    assert pending[1].title == "Task 1"


async def test_mark_completed(store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Complete me",
        description="Test completion",
    )
    await store.save(task)
    result = {"pr_url": "https://github.com/test/pr/1"}
    await store.mark_completed(task.id, result)
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.COMPLETED
    assert loaded.result == result
    assert loaded.completed_at is not None


async def test_mark_failed(store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Fail me",
        description="Test failure",
    )
    await store.save(task)
    await store.mark_failed(task.id, error="Something broke")
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.FAILED
    assert loaded.handler_data["error"] == "Something broke"


def _new_task() -> Task:
    return Task.new(task_type=TaskType.ECHO, source=TaskSource.CHAT, title="t", description="d")


async def test_mark_failed_records_kind(store):
    task = _new_task()
    await store.save(task)
    await store.mark_failed(task.id, error="boom", kind="transient")
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.FAILED
    assert loaded.failure_kind == "transient"
    assert loaded.handler_data["error"] == "boom"


async def test_list_pending_excludes_future_available_at(store):
    future = _new_task()
    await store.save(future)
    await store.requeue(
        future.id,
        retries=1,
        available_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        error="retry me",
        kind="transient",
    )
    ready = _new_task()
    await store.save(ready)

    pending = await store.list_pending(limit=10)
    ids = {t.id for t in pending}
    assert ready.id in ids
    assert future.id not in ids


async def test_requeue_sets_status_retries_and_kind(store):
    task = _new_task()
    await store.save(task)
    await store.requeue(task.id, retries=2, available_at=None, error="e", kind="timeout")
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.QUEUED
    assert loaded.retries == 2
    assert loaded.failure_kind == "timeout"


async def test_list_active_tasks_returns_only_active(store):
    queued = _new_task()
    await store.save(queued)
    executing = _new_task()
    await store.save(executing)
    await store.update_status(executing.id, TaskStatus.EXECUTING)

    active = await store.list_active_tasks()
    ids = {t.id for t in active}
    assert executing.id in ids
    assert queued.id not in ids


async def test_clear_for_retry_resets_budget(store):
    task = _new_task()
    await store.save(task)
    await store.requeue(
        task.id, retries=3, available_at="2099-01-01T00:00:00+00:00", kind="timeout"
    )
    await store.mark_failed(task.id, error="dead", kind="timeout")

    await store.clear_for_retry(task.id)
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.QUEUED
    assert loaded.retries == 0
    assert loaded.available_at is None
    assert loaded.failure_kind is None
