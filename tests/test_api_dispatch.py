import pytest
from httpx import ASGITransport, AsyncClient

from forge.db import Database
from forge.main import create_app
from forge.api import tasks as tasks_api
from forge.models import TaskSource, TaskStatus


@pytest.fixture
async def client():
    db = Database(":memory:")
    await db.initialize()
    app = create_app(db=db)
    # create_app already built a TaskStore and registered it via set_store;
    # reuse that instance rather than constructing a second one over the same db.
    store = tasks_api.get_store()

    nudged = {"count": 0}

    class StubCoordinator:
        def nudge(self) -> None:
            nudged["count"] += 1

    tasks_api.set_coordinator(StubCoordinator())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, store, nudged
    # Reset the module-level coordinator so the stub can't leak into other tests.
    tasks_api.set_coordinator(None)
    await db.close()


async def test_create_task_uses_manual_source_and_nudges(client):
    c, store, nudged = client
    resp = await c.post(
        "/api/tasks",
        json={"type": "code", "title": "do a thing", "description": "the details", "repo": "t-eckert/x"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["source"] == "manual"
    assert body["status"] == TaskStatus.QUEUED.value
    saved = await store.get(body["id"])
    assert saved is not None
    assert saved.source == TaskSource.MANUAL
    assert nudged["count"] == 1
