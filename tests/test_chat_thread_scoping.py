"""Phase P₂ commit (a) — chat.py persists to ThreadStore when thread_id is given.

Preserves the singleton-log path for requests without a thread_id (the Today
composer), and routes thread-scoped requests through ThreadStore so message
history, list-messages, and downstream dispatch all live under the thread.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from forge.api import chat
from forge.db import Database
from forge.main import create_app
from forge.store import TaskStore
from forge.thread_store import ThreadStore


@pytest.fixture
async def client_with_thread_store():
    db = Database(":memory:")
    await db.initialize()
    store = TaskStore(db)
    thread_store = ThreadStore(db)
    app = create_app(db)
    chat.configure(store=store, thread_store=thread_store, anthropic_api_key=None)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c, thread_store, store
    await db.close()


async def test_thread_scoped_message_persists_to_thread_store(client_with_thread_store):
    c, thread_store, task_store = client_with_thread_store
    thread = await thread_store.create(title="Dispatch smoke", kind="code+tools")

    resp = await c.post("/api/chat", json={"content": "Hello", "thread_id": thread.id})
    assert resp.status_code == 200
    assert "not configured" in resp.text.lower()  # no API key in test env

    # User + assistant fallback both landed in the thread, not the singleton log.
    msgs = await thread_store.list_messages(thread.id)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[0].content == "Hello"
    assert "not configured" in msgs[1].content.lower()

    # Singleton log stays empty.
    assert await task_store.list_chat_messages() == []


async def test_threadless_message_still_uses_singleton_log(client_with_thread_store):
    c, thread_store, task_store = client_with_thread_store

    resp = await c.post("/api/chat", json={"content": "Hi without thread"})
    assert resp.status_code == 200

    # Singleton log got both messages; no threads were touched.
    assert len(await task_store.list_chat_messages()) == 2
    assert await thread_store.list() == []


async def test_unknown_thread_id_returns_404(client_with_thread_store):
    c, *_ = client_with_thread_store

    resp = await c.post(
        "/api/chat", json={"content": "Hello", "thread_id": "thread-nope"}
    )
    assert resp.status_code == 404
    assert "thread not found" in resp.text.lower()
