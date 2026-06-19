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


async def test_follow_up_creates_linked_task(client, tmp_path):
    c, store, nudged = client
    wt = tmp_path / "wt"
    wt.mkdir()
    parent = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="p", description="d", repo="o/r", require_approval=True)
    await store.save(parent)
    await store.update_status(parent.id, TaskStatus.COMPLETED)
    await store.update_handler_data(parent.id, {"worktree_path": str(wt)})

    resp = await c.post(f"/api/tasks/{parent.id}/follow-up", json={"prompt": "also add logging"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["continues_task_id"] == parent.id
    assert body["repo"] == "o/r"
    assert body["require_approval"] is True
    assert body["status"] == "queued"
    # The coordinator must be nudged so the follow-up runs promptly, not on the next poll.
    assert nudged["count"] == 1


async def test_follow_up_allowed_at_approval_gate(client, tmp_path):
    c, store, _ = client
    wt = tmp_path / "wt-gate"
    wt.mkdir()
    parent = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="p", description="d", repo="o/r")
    await store.save(parent)
    await store.update_status(parent.id, TaskStatus.AWAITING_APPROVAL)
    await store.update_handler_data(parent.id, {"worktree_path": str(wt)})

    resp = await c.post(f"/api/tasks/{parent.id}/follow-up", json={"prompt": "tweak it"})
    assert resp.status_code == 200
    assert resp.json()["continues_task_id"] == parent.id


async def test_follow_up_rejects_active_parent(client, tmp_path):
    c, store, _ = client
    wt = tmp_path / "wt2"
    wt.mkdir()
    parent = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="p", description="d", repo="o/r")
    await store.save(parent)
    await store.update_status(parent.id, TaskStatus.EXECUTING)
    await store.update_handler_data(parent.id, {"worktree_path": str(wt)})

    resp = await c.post(f"/api/tasks/{parent.id}/follow-up", json={"prompt": "x"})
    assert resp.status_code == 409


async def test_follow_up_rejects_reaped_worktree(client, tmp_path):
    c, store, _ = client
    parent = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="p", description="d", repo="o/r")
    await store.save(parent)
    await store.update_status(parent.id, TaskStatus.COMPLETED)
    await store.update_handler_data(parent.id, {"worktree_path": str(tmp_path / "gone")})

    resp = await c.post(f"/api/tasks/{parent.id}/follow-up", json={"prompt": "x"})
    assert resp.status_code == 409


async def test_follow_up_missing_parent_404(client):
    c, _, _ = client
    resp = await c.post("/api/tasks/does-not-exist/follow-up", json={"prompt": "x"})
    assert resp.status_code == 404
