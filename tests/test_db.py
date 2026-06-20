import pytest

from forge.db import Database
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


async def test_initialize_creates_tables(db: Database):
    tables = await db.fetch_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    table_names = [row["name"] for row in tables]
    assert "tasks" in table_names
    assert "task_logs" in table_names
    assert "schedules" in table_names


async def test_insert_and_fetch_task(db: Database):
    await db.execute(
        """INSERT INTO tasks (id, type, status, source, title, description, handler_data, retries, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
        ("01TASK001", "code", "queued", "chat", "Test task", "A test", "{}", 0),
    )
    row = await db.fetch_one("SELECT * FROM tasks WHERE id = ?", ("01TASK001",))
    assert row is not None
    assert row["title"] == "Test task"
    assert row["status"] == "queued"
    assert row["type"] == "code"


async def test_update_task_status(db: Database):
    await db.execute(
        """INSERT INTO tasks (id, type, status, source, title, description, handler_data, retries, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
        ("01TASK002", "code", "queued", "chat", "Update me", "Test", "{}", 0),
    )
    await db.execute(
        "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE id = ?",
        ("executing", "01TASK002"),
    )
    row = await db.fetch_one("SELECT status FROM tasks WHERE id = ?", ("01TASK002",))
    assert row["status"] == "executing"


async def test_tasks_table_has_resilience_columns():
    from forge.db import Database

    db = Database(":memory:")
    await db.initialize()
    try:
        rows = await db.fetch_all("PRAGMA table_info(tasks)")
        names = {r["name"] for r in rows}
        assert {"max_retries", "available_at", "failure_kind"} <= names
    finally:
        await db.close()


async def test_task_require_approval_roundtrips(store):
    from forge.models import Task, TaskType, TaskSource
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="gated", description="needs approval", require_approval=True)
    await store.save(task)
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.require_approval is True


async def test_continues_task_id_roundtrip(store):
    from forge.models import Task, TaskSource, TaskType

    parent = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="p", description="d")
    await store.save(parent)
    child = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.MANUAL,
        title="c",
        description="follow up",
        continues_task_id=parent.id,
    )
    await store.save(child)

    loaded = await store.get(child.id)
    assert loaded.continues_task_id == parent.id

    # Default is None for a non-follow-up task.
    loaded_parent = await store.get(parent.id)
    assert loaded_parent.continues_task_id is None
