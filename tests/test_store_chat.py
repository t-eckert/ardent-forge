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


async def test_save_and_list_chat_messages(store):
    await store.save_chat_message(role="user", content="Hello")
    await store.save_chat_message(role="assistant", content="Hi there!")
    messages = await store.list_chat_messages()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hi there!"


async def test_chat_messages_ordered_by_created_at(store):
    await store.save_chat_message(role="user", content="First")
    await store.save_chat_message(role="user", content="Second")
    messages = await store.list_chat_messages()
    assert messages[0]["content"] == "First"
    assert messages[1]["content"] == "Second"


async def test_chat_message_has_id_and_timestamp(store):
    await store.save_chat_message(role="user", content="Test")
    messages = await store.list_chat_messages()
    assert messages[0]["id"] is not None
    assert messages[0]["created_at"] is not None


async def test_clear_chat_messages(store):
    await store.save_chat_message(role="user", content="Hello")
    await store.clear_chat_messages()
    messages = await store.list_chat_messages()
    assert len(messages) == 0
