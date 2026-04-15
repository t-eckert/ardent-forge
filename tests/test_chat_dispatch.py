"""Phase P₂b — dispatch_task meta-tool branch in chat.py.

When Claude emits a ``dispatch_task`` tool_use block, the chat endpoint
should:
 - create a Task row with source=CHAT
 - link it to the origin thread via thread_tasks
 - append a 'task-dispatched' variant message to the thread with the
   Claude tool_use_id so we can correlate later
 - return a queued receipt as the tool_result (no blocking on coordinator)

Errors surface as tool_results with is_error=True so Claude can recover
in the same turn.
"""

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from forge.agents import AgentContext, AgentRegistry
from forge.api import chat
from forge.connectors import ConnectorRegistry
from forge.db import Database
from forge.main import create_app
from forge.orchestrator import ForgeOrchestrator
from forge.models import TaskStatus
from forge.store import TaskStore
from forge.thread_store import ThreadStore


# ─── Fakes ──────────────────────────────────────────────────────────────────


class ResearchAgent:
    name = "research-agent"
    task_type = "research"
    stages = ["execute"]
    connectors: list[str] = []

    async def execute(self, task, ctx: AgentContext):
        return {"ok": True}


class FakeStreamContext:
    def __init__(self, text_chunks, final_message):
        self._chunks = text_chunks
        self._final = final_message

    async def __aenter__(self):
        async def _gen():
            for c in self._chunks:
                yield c

        self.text_stream = _gen()
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_final_message(self):
        return self._final


def make_tool_use_block(tool_id, name, input_):
    b = MagicMock()
    b.type = "tool_use"
    b.id = tool_id
    b.name = name
    b.input = input_
    return b


def make_text_block(text):
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


# ─── Fixture ────────────────────────────────────────────────────────────────


@pytest.fixture
async def wired():
    db = Database(":memory:")
    await db.initialize()
    store = TaskStore(db)
    thread_store = ThreadStore(db)

    agents = AgentRegistry()
    agents.register(ResearchAgent())
    orchestrator = ForgeOrchestrator(
        connectors=ConnectorRegistry(),
        agents=agents,
        store=store,
        thread_store=thread_store,
    )

    app = create_app(db)
    chat.configure(
        store=store,
        thread_store=thread_store,
        orchestrator=orchestrator,
        anthropic_api_key="fake-key",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, thread_store, store, orchestrator
    await db.close()
    # Reset module state so other tests start clean.
    chat.configure(store=store, anthropic_api_key=None)


def _fake_claude_emitting_dispatch(title, task_type, description):
    """Two-turn Anthropic script: dispatch then a closing text message."""
    dispatch_msg = MagicMock()
    dispatch_msg.stop_reason = "tool_use"
    dispatch_msg.content = [
        make_tool_use_block(
            "toolu_d1",
            "dispatch_task",
            {"task_type": task_type, "title": title, "description": description},
        )
    ]

    final = MagicMock()
    final.stop_reason = "end_turn"
    final.content = [make_text_block("Dispatched. I'll let you know when it lands.")]

    fake = MagicMock()
    fake.messages = MagicMock()
    fake.messages.stream = MagicMock(
        side_effect=[
            FakeStreamContext([], dispatch_msg),
            FakeStreamContext(["Dispatched. I'll let you know when it lands."], final),
        ]
    )
    return fake


# ─── Tests ──────────────────────────────────────────────────────────────────


async def test_dispatch_creates_task_and_links_thread(wired):
    c, thread_store, task_store, _ = wired
    thread = await thread_store.create(title="Research Svelte 5", kind="code+tools")

    fake = _fake_claude_emitting_dispatch(
        "Research Svelte 5 breaking changes", "research", "Collect notes + sources"
    )
    chat.set_anthropic_client_factory(lambda key: fake)

    resp = await c.post(
        "/api/chat",
        json={"content": "Research Svelte 5 breaking changes", "thread_id": thread.id},
    )
    assert resp.status_code == 200

    msgs = await thread_store.list_messages(thread.id)
    roles_variants = [(m.role, m.variant) for m in msgs]
    # user → assistant task-dispatched → assistant text
    assert roles_variants == [
        ("user", "text"),
        ("assistant", "task-dispatched"),
        ("assistant", "text"),
    ]

    dispatch_msg = msgs[1]
    assert dispatch_msg.task_id is not None
    assert dispatch_msg.tool_use_id == "toolu_d1"

    # Task was created, source=chat, status=queued, linked as origin.
    tasks = await task_store.list_by_status(TaskStatus.QUEUED)
    assert len(tasks) == 1
    task = tasks[0]
    assert str(task.type) == "research"
    assert task.source.value == "chat"
    assert await thread_store.origin_thread_for(task.id) == thread.id


async def test_dispatch_without_thread_surfaces_as_tool_error(wired):
    c, thread_store, task_store, _ = wired

    fake = _fake_claude_emitting_dispatch("Ghost research", "research", "no thread")
    chat.set_anthropic_client_factory(lambda key: fake)

    # No thread_id in the request — dispatch should fail as a tool error,
    # Claude then emits a closing text message and the endpoint returns 200.
    resp = await c.post("/api/chat", json={"content": "Research"})
    assert resp.status_code == 200

    # No task was created and no thread exists to dispatch into.
    assert await task_store.list_by_status(TaskStatus.QUEUED) == []
    assert await thread_store.list() == []


async def test_dispatch_unknown_task_type_surfaces_error(wired):
    c, thread_store, task_store, _ = wired
    thread = await thread_store.create(title="Bad dispatch")

    fake = _fake_claude_emitting_dispatch("Garbage", "nonsense-type", "…")
    chat.set_anthropic_client_factory(lambda key: fake)

    resp = await c.post("/api/chat", json={"content": "Go!", "thread_id": thread.id})
    assert resp.status_code == 200

    # No Task created — invalid task_type rejected at the dispatch branch.
    assert await task_store.list_by_status(TaskStatus.QUEUED) == []
    # Thread still got the user message and the closing assistant text, but
    # NO task-dispatched card.
    msgs = await thread_store.list_messages(thread.id)
    variants = [m.variant for m in msgs]
    assert "task-dispatched" not in variants
