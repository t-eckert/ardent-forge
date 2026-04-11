import pytest
from httpx import ASGITransport, AsyncClient

from forge.api import chat
from forge.db import Database
from forge.main import create_app
from forge.store import TaskStore


@pytest.fixture
async def client():
    db = Database(":memory:")
    await db.initialize()
    store = TaskStore(db)
    app = create_app(db)
    chat.configure(store=store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    await db.close()


async def test_list_messages_empty(client):
    resp = await client.get("/api/chat/messages")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_send_message_no_api_key(client):
    resp = await client.post("/api/chat", json={"content": "Hello"})
    assert resp.status_code == 200
    assert "not configured" in resp.text.lower()


async def test_messages_persisted(client):
    await client.post("/api/chat", json={"content": "Hello"})
    resp = await client.get("/api/chat/messages")
    messages = resp.json()
    assert len(messages) == 2  # user + assistant
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"


async def test_clear_messages(client):
    await client.post("/api/chat", json={"content": "Hello"})
    resp = await client.delete("/api/chat/messages")
    assert resp.status_code == 200
    resp = await client.get("/api/chat/messages")
    assert resp.json() == []
