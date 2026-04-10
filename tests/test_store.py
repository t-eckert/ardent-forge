import pytest

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
