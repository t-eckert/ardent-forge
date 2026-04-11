import pytest
from httpx import ASGITransport, AsyncClient

from forge.api import schedules
from forge.db import Database
from forge.main import create_app
from forge.store import TaskStore


@pytest.fixture
async def client():
    db = Database(":memory:")
    await db.initialize()
    store = TaskStore(db)
    app = create_app(db)
    schedules.set_store(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    await db.close()


async def test_list_schedules_empty(client):
    resp = await client.get("/api/schedules")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_schedule(client):
    resp = await client.post(
        "/api/schedules",
        json={
            "name": "Weekly report",
            "cron_expr": "0 9 * * 1",
            "task_type": "report",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Weekly report"
    assert data["enabled"] == 1


async def test_delete_schedule(client):
    resp = await client.post(
        "/api/schedules",
        json={"name": "Test", "cron_expr": "* * * * *", "task_type": "echo"},
    )
    schedule_id = resp.json()["id"]
    resp = await client.delete(f"/api/schedules/{schedule_id}")
    assert resp.status_code == 200
    resp = await client.get("/api/schedules")
    assert resp.json() == []


async def test_delete_nonexistent_schedule(client):
    resp = await client.delete("/api/schedules/nonexistent")
    assert resp.status_code == 404


async def test_toggle_schedule(client):
    resp = await client.post(
        "/api/schedules",
        json={"name": "Test", "cron_expr": "* * * * *", "task_type": "echo"},
    )
    schedule_id = resp.json()["id"]
    resp = await client.patch(
        f"/api/schedules/{schedule_id}", json={"enabled": False}
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] == 0
