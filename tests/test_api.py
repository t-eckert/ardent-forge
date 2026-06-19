import pytest
from httpx import ASGITransport, AsyncClient

from forge.db import Database
from forge.main import create_app


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def client(db):
    app = create_app(db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_create_task(client):
    resp = await client.post(
        "/api/tasks",
        json={
            "type": "echo",
            "title": "Test task",
            "description": "Created via API",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test task"
    assert data["status"] == "queued"
    assert data["source"] == "manual"
    assert "id" in data


async def test_get_task(client):
    create_resp = await client.post(
        "/api/tasks",
        json={
            "type": "code",
            "title": "Get me",
            "description": "Fetch test",
        },
    )
    task_id = create_resp.json()["id"]

    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Get me"


async def test_get_nonexistent_task(client):
    resp = await client.get("/api/tasks/nonexistent")
    assert resp.status_code == 404


async def test_list_tasks(client):
    for i in range(3):
        await client.post(
            "/api/tasks",
            json={
                "type": "code",
                "title": f"Task {i}",
                "description": f"List test {i}",
            },
        )

    resp = await client.get("/api/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3


async def test_list_tasks_filter_by_status(client):
    await client.post(
        "/api/tasks",
        json={"type": "code", "title": "Queued", "description": "Will stay queued"},
    )

    resp = await client.get("/api/tasks?status=queued")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await client.get("/api/tasks?status=completed")
    assert resp.status_code == 200
    assert len(resp.json()) == 0



async def test_manual_retry_requeues_failed_task(client):
    from forge.api.tasks import get_store
    from forge.models import TaskStatus

    create = await client.post(
        "/api/tasks",
        json={"type": "echo", "title": "t", "description": "d"},
    )
    task_id = create.json()["id"]

    store = get_store()
    await store.mark_failed(task_id, error="boom", kind="timeout")

    resp = await client.post(f"/api/tasks/{task_id}/retry")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["retries"] == 0
    assert body["failure_kind"] is None

    loaded = await store.get(task_id)
    assert loaded.status == TaskStatus.QUEUED


async def test_manual_retry_rejects_non_failed(client):
    create = await client.post(
        "/api/tasks",
        json={"type": "echo", "title": "t", "description": "d"},
    )
    task_id = create.json()["id"]  # status queued, not failed

    resp = await client.post(f"/api/tasks/{task_id}/retry")
    assert resp.status_code == 409


async def test_manual_retry_unknown_task_404(client):
    resp = await client.post("/api/tasks/does-not-exist/retry")
    assert resp.status_code == 404
