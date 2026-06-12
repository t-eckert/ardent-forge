"""Phase R(a) — /api/threads/{id} embeds linked Task summaries on
task-dispatched / task-resolved messages so the UI can render rich cards
without N+1 fetches.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from forge.agents import AgentContext, AgentRegistry
from forge.api import tasks as tasks_api
from forge.connectors import ConnectorRegistry
from forge.db import Database
from forge.main import create_app
from forge.models import Task, TaskSource, TaskStatus, TaskType
from forge.orchestrator import ForgeOrchestrator
from forge.store import TaskStore
from forge.thread_store import ThreadStore


class ResearchAgent:
    name = "research-agent"
    task_type = "code"
    stages = ["triage", "execute", "verify", "deliver"]
    connectors: list[str] = []

    async def execute(self, task, ctx: AgentContext):
        return {"ok": True}


@pytest.fixture
async def client():
    db = Database(":memory:")
    await db.initialize()
    task_store = TaskStore(db)
    thread_store = ThreadStore(db)

    agents = AgentRegistry()
    agents.register(ResearchAgent())
    orchestrator = ForgeOrchestrator(
        connectors=ConnectorRegistry(),
        agents=agents,
        store=task_store,
        thread_store=thread_store,
    )

    app = create_app(db)
    app.state.thread_store = thread_store
    app.state.orchestrator = orchestrator
    tasks_api.set_store(task_store)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, thread_store, task_store
    await db.close()


async def test_dispatched_message_embeds_task_summary(client):
    c, thread_store, task_store = client
    thread = await thread_store.create(title="Research Svelte 5", kind="code+tools")

    task = Task.new(
        task_type=TaskType("code"),
        source=TaskSource.CHAT,
        title="Svelte 5 notes",
        description="…",
    )
    await task_store.save(task)
    await thread_store.link_task(thread_id=thread.id, task_id=task.id, relation="origin")
    await thread_store.append_message(
        thread_id=thread.id,
        role="assistant",
        content="dispatched code — Svelte 5 migration",
        variant="task-dispatched",
        task_id=task.id,
        tool_use_id="toolu_abc",
    )

    resp = await c.get(f"/api/threads/{thread.id}")
    assert resp.status_code == 200
    msg = resp.json()["messages"][0]
    assert msg["variant"] == "task-dispatched"
    assert msg["tool_use_id"] == "toolu_abc"

    task_summary = msg["task"]
    assert task_summary["id"] == task.id
    assert task_summary["type"] == "code"
    assert task_summary["status"] == "queued"
    assert task_summary["current_stage"] == "triage"
    assert task_summary["stages"] == ["triage", "execute", "verify", "deliver"]
    assert task_summary["result"] is None  # not yet completed


async def test_resolved_message_carries_result_and_nulls_stage(client):
    c, thread_store, task_store = client
    thread = await thread_store.create(title="Done work")

    task = Task.new(
        task_type=TaskType("code"),
        source=TaskSource.CHAT,
        title="Completed research",
        description="…",
    )
    await task_store.save(task)
    await task_store.mark_completed(task.id, {"files": ["a.md"], "ok": True})

    await thread_store.link_task(thread_id=thread.id, task_id=task.id, relation="origin")
    await thread_store.append_message(
        thread_id=thread.id,
        role="assistant",
        content="code finished — completed work",
        variant="task-resolved",
        task_id=task.id,
    )

    resp = await c.get(f"/api/threads/{thread.id}")
    msg = resp.json()["messages"][0]
    assert msg["variant"] == "task-resolved"
    task_summary = msg["task"]
    assert task_summary["status"] == "completed"
    assert task_summary["current_stage"] is None
    assert task_summary["result"] == {"files": ["a.md"], "ok": True}
    assert task_summary["completed_at"] is not None


async def test_text_message_is_not_enriched(client):
    c, thread_store, _ = client
    thread = await thread_store.create(title="Plain chat")
    await thread_store.append_message(
        thread_id=thread.id, role="user", content="hi"
    )

    resp = await c.get(f"/api/threads/{thread.id}")
    msg = resp.json()["messages"][0]
    assert "task" not in msg


async def test_missing_task_row_yields_null_task(client):
    c, thread_store, _ = client
    thread = await thread_store.create(title="Ghost")
    # Reference a task_id that has no row — simulates a deleted task.
    await thread_store.append_message(
        thread_id=thread.id,
        role="assistant",
        content="dispatched",
        variant="task-dispatched",
        task_id="01ZZZZZZZZZZZZZZZZZZZZZZZZ",
    )
    resp = await c.get(f"/api/threads/{thread.id}")
    msg = resp.json()["messages"][0]
    assert msg["task"] is None
