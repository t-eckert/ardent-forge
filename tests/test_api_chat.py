import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response
from unittest.mock import MagicMock

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


# ---------------------------------------------------------------------------
# Tool-use loop tests
# ---------------------------------------------------------------------------


class FakeStreamContext:
    """Mimics the Anthropic async-context-manager streaming response.

    The chat code does:
        async with client.messages.stream(...) as stream:
            async for text in stream.text_stream: ...
            final_message = await stream.get_final_message()

    text_stream must be an async iterable.  We set it as a plain attribute
    (an async generator object) so that ``async for`` works without any
    descriptor gymnastics.
    """

    def __init__(self, text_chunks, final_message):
        self._text_chunks = text_chunks
        self._final_message = final_message

    async def __aenter__(self):
        # Build the async generator once and attach it as an attribute so
        # ``stream.text_stream`` returns it directly (no awaiting needed).
        async def _gen():
            for chunk in self._text_chunks:
                yield chunk

        self.text_stream = _gen()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get_final_message(self):
        return self._final_message


def make_text_block(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def make_tool_use_block(tool_id, name, input_):
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = input_
    return block


@respx.mock
async def test_chat_invokes_weather_tool(client):
    # Mock The Weather service (default Ottawa call — no lat/lon params)
    respx.get("http://127.0.0.1:8091/").mock(
        return_value=Response(
            200,
            json={
                "current": {
                    "dt": 1775963321,
                    "temp": 280.97,
                    "feels_like": 279.5,
                    "humidity": 80,
                    "wind_speed": 3.5,
                    "weather": [{"description": "overcast clouds"}],
                },
                "daily": [],
            },
        )
    )

    # Two-turn fake Anthropic conversation:
    # Turn 1: assistant emits a tool_use block (no text)
    # Turn 2: assistant emits final text
    tool_use_msg = MagicMock()
    tool_use_msg.stop_reason = "tool_use"
    tool_use_msg.content = [make_tool_use_block("toolu_1", "get_weather", {})]

    final_msg = MagicMock()
    final_msg.stop_reason = "end_turn"
    final_msg.content = [make_text_block("It's 8°C and overcast in Ottawa.")]

    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.stream = MagicMock(side_effect=[
        FakeStreamContext([], tool_use_msg),
        FakeStreamContext(["It's 8°C and overcast in Ottawa."], final_msg),
    ])

    original_factory = chat._anthropic_client_factory
    try:
        chat.set_anthropic_client_factory(lambda key: fake_client)
        chat.configure(store=chat._store, anthropic_api_key="fake-key")

        resp = await client.post("/api/chat", json={"content": "what's the weather?"})
        assert resp.status_code == 200
        assert "Ottawa" in resp.text or "overcast" in resp.text.lower()
    finally:
        chat.set_anthropic_client_factory(original_factory)
        chat.configure(store=chat._store, anthropic_api_key=None)
