import pytest
from forge.db import Database
from forge.store import TaskStore


@pytest.fixture
async def store():
    db = Database(":memory:")
    await db.initialize()
    s = TaskStore(db)
    yield s
    await db.close()


async def test_save_and_list_schedules(store):
    schedule_id = await store.save_schedule(
        name="Weekly report",
        cron_expr="0 9 * * 1",
        task_type="report",
        task_template={"title": "Weekly report"},
    )
    schedules = await store.list_schedules()
    assert len(schedules) == 1
    assert schedules[0]["name"] == "Weekly report"
    assert schedules[0]["cron_expr"] == "0 9 * * 1"
    assert schedules[0]["enabled"] == 1
    assert schedules[0]["id"] == schedule_id


async def test_delete_schedule(store):
    schedule_id = await store.save_schedule(
        name="Test",
        cron_expr="* * * * *",
        task_type="echo",
    )
    await store.delete_schedule(schedule_id)
    schedules = await store.list_schedules()
    assert len(schedules) == 0


async def test_toggle_schedule(store):
    schedule_id = await store.save_schedule(
        name="Test",
        cron_expr="* * * * *",
        task_type="echo",
    )
    await store.update_schedule_enabled(schedule_id, False)
    schedules = await store.list_schedules()
    assert schedules[0]["enabled"] == 0


async def test_get_schedule(store):
    schedule_id = await store.save_schedule(
        name="Test",
        cron_expr="* * * * *",
        task_type="echo",
    )
    schedule = await store.get_schedule(schedule_id)
    assert schedule is not None
    assert schedule["name"] == "Test"


async def test_get_nonexistent_schedule(store):
    schedule = await store.get_schedule("nonexistent")
    assert schedule is None
