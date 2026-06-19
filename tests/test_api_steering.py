import pytest
from httpx import ASGITransport, AsyncClient

from forge.db import Database
from forge.main import create_app
from forge.api import tasks as tasks_api
from forge.models import Task, TaskType, TaskSource, TaskStatus


@pytest.fixture
async def client():
    db = Database(":memory:")
    await db.initialize()
    app = create_app(db=db)
    store = tasks_api.get_store()

    nudged = {"count": 0}

    class StubCoordinator:
        def nudge(self) -> None:
            nudged["count"] += 1

    tasks_api.set_coordinator(StubCoordinator())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, store, nudged
    tasks_api.set_coordinator(None)
    await db.close()


async def _seed(store, status):
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d")
    await store.save(task)
    await store.update_status(task.id, status)
    return task.id


async def test_cancel_running_task(client):
    c, store, _ = client
    tid = await _seed(store, TaskStatus.EXECUTING)
    resp = await c.post(f"/api/tasks/{tid}/cancel")
    assert resp.status_code == 200
    assert (await store.get(tid)).status == TaskStatus.CANCELLED


async def test_cancel_terminal_task_409(client):
    c, store, _ = client
    tid = await _seed(store, TaskStatus.COMPLETED)
    resp = await c.post(f"/api/tasks/{tid}/cancel")
    assert resp.status_code == 409


async def test_approve_sets_delivering_and_nudges(client):
    c, store, nudged = client
    tid = await _seed(store, TaskStatus.AWAITING_APPROVAL)
    resp = await c.post(f"/api/tasks/{tid}/approve")
    assert resp.status_code == 200
    assert (await store.get(tid)).status == TaskStatus.DELIVERING
    assert nudged["count"] == 1


async def test_approve_wrong_state_409(client):
    c, store, _ = client
    tid = await _seed(store, TaskStatus.EXECUTING)
    resp = await c.post(f"/api/tasks/{tid}/approve")
    assert resp.status_code == 409


async def test_reject_cancels(client):
    c, store, _ = client
    tid = await _seed(store, TaskStatus.AWAITING_APPROVAL)
    resp = await c.post(f"/api/tasks/{tid}/reject")
    assert resp.status_code == 200
    assert (await store.get(tid)).status == TaskStatus.CANCELLED


async def test_cancel_unknown_404(client):
    c, _, _ = client
    resp = await c.post("/api/tasks/nonexistent/cancel")
    assert resp.status_code == 404
