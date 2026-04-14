"""/api/threads endpoint tests."""

import pytest
from fastapi.testclient import TestClient

from forge.db import Database
from forge.main import create_app
from forge.thread_store import ThreadStore


@pytest.fixture
async def client(db: Database):
    app = create_app(db)
    app.state.thread_store = ThreadStore(db)
    # Seed a task row so link_task tests have a valid FK target.
    await db.execute(
        "INSERT INTO tasks (id, type, status, source, title, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("task-a", "code", "queued", "chat", "t", "d", "now", "now"),
    )
    yield TestClient(app)


def test_list_empty(client):
    r = client.get("/api/threads")
    assert r.status_code == 200
    assert r.json() == []


def test_create_list_get(client):
    r = client.post("/api/threads", json={"title": "Morning briefing", "kind": "code+tools"})
    assert r.status_code == 200
    created = r.json()
    assert created["title"] == "Morning briefing"
    assert created["kind"] == "code+tools"

    assert len(client.get("/api/threads").json()) == 1

    g = client.get(f"/api/threads/{created['id']}")
    assert g.status_code == 200
    payload = g.json()
    assert payload["id"] == created["id"]
    assert payload["messages"] == []


def test_get_missing_404(client):
    assert client.get("/api/threads/nope").status_code == 404


def test_append_message_and_reread(client):
    thread = client.post("/api/threads", json={"title": "t"}).json()

    m = client.post(
        f"/api/threads/{thread['id']}/messages",
        json={"role": "user", "content": "hello"},
    ).json()
    assert m["role"] == "user"
    assert m["content"] == "hello"
    assert m["variant"] == "text"

    client.post(
        f"/api/threads/{thread['id']}/messages",
        json={
            "role": "assistant",
            "content": "18°C, clear",
            "variant": "widget",
            "widgets": [{"tool": "weather.forecast", "currentC": 18}],
        },
    )

    full = client.get(f"/api/threads/{thread['id']}").json()
    assert len(full["messages"]) == 2
    assert full["messages"][1]["widgets"][0]["currentC"] == 18


def test_link_task_origin_and_listing(client):
    thread = client.post("/api/threads", json={"title": "t"}).json()

    r = client.post(
        f"/api/threads/{thread['id']}/tasks",
        json={"task_id": "task-a", "relation": "origin"},
    )
    assert r.status_code == 200

    rows = client.get(f"/api/threads/{thread['id']}/tasks").json()
    assert len(rows) == 1
    assert rows[0]["task_id"] == "task-a"
    assert rows[0]["relation"] == "origin"


def test_link_bad_relation_400(client):
    thread = client.post("/api/threads", json={"title": "t"}).json()
    r = client.post(
        f"/api/threads/{thread['id']}/tasks",
        json={"task_id": "task-a", "relation": "nope"},
    )
    # Pydantic validates the Literal['origin','referenced'] and 422s before
    # reaching the handler; either 400 or 422 is acceptable evidence of rejection.
    assert r.status_code in (400, 422)


def test_link_to_missing_thread_404(client):
    r = client.post(
        "/api/threads/ghost/tasks",
        json={"task_id": "task-a", "relation": "origin"},
    )
    assert r.status_code == 404
