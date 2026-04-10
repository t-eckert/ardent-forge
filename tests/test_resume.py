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


async def test_reset_in_progress_tasks(store):
    """On startup, any task stuck in a non-terminal active state should be reset to queued."""
    task_executing = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Was executing",
        description="Stuck",
    )
    await store.save(task_executing)
    await store.update_status(task_executing.id, TaskStatus.EXECUTING)

    task_verifying = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Was verifying",
        description="Also stuck",
    )
    await store.save(task_verifying)
    await store.update_status(task_verifying.id, TaskStatus.VERIFYING)

    task_completed = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Already done",
        description="Should not change",
    )
    await store.save(task_completed)
    await store.mark_completed(task_completed.id, {"done": True})

    reset_count = await store.reset_active_tasks()
    assert reset_count == 2

    t1 = await store.get(task_executing.id)
    assert t1 is not None
    assert t1.status == TaskStatus.QUEUED

    t2 = await store.get(task_verifying.id)
    assert t2 is not None
    assert t2.status == TaskStatus.QUEUED

    t3 = await store.get(task_completed.id)
    assert t3 is not None
    assert t3.status == TaskStatus.COMPLETED
