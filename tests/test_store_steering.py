import pytest

from forge.db import Database
from forge.models import Task, TaskType, TaskSource, TaskStatus
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


async def _make(store, status):
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d")
    await store.save(task)
    await store.update_status(task.id, status)
    return task.id


async def test_mark_cancelled_sets_status(store):
    tid = await _make(store, TaskStatus.EXECUTING)
    await store.mark_cancelled(tid)
    assert (await store.get(tid)).status == TaskStatus.CANCELLED


async def test_mark_approved_sets_delivering(store):
    tid = await _make(store, TaskStatus.AWAITING_APPROVAL)
    await store.mark_approved(tid)
    assert (await store.get(tid)).status == TaskStatus.DELIVERING
