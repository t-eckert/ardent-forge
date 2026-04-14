"""End-to-end test: a task with an origin thread completes via the coordinator,
and the orchestrator posts a resolution message back into that thread."""

import pytest

from forge.agents import AgentContext, AgentRegistry
from forge.connectors import ConnectorRegistry
from forge.coordinator import Coordinator
from forge.db import Database
from forge.models import Task, TaskSource, TaskType
from forge.orchestrator import ForgeOrchestrator
from forge.store import TaskStore
from forge.thread_store import ThreadStore


class FakeCodeAgent:
    name = "code-agent"
    task_type = "code"
    stages = ["execute"]
    connectors: list[str] = []

    async def execute(self, task, ctx: AgentContext):
        return {"pr_url": f"https://github.com/foo/pull/42#{task.id[:6]}"}


@pytest.fixture
async def wired(db: Database):
    store = TaskStore(db)
    thread_store = ThreadStore(db)
    agents = AgentRegistry()
    agents.register(FakeCodeAgent())
    orchestrator = ForgeOrchestrator(
        connectors=ConnectorRegistry(),
        agents=agents,
        store=store,
        thread_store=thread_store,
    )
    coordinator = Coordinator(
        store=store,
        registry=agents,
        orchestrator=orchestrator,
        max_concurrent=2,
    )
    return store, thread_store, orchestrator, coordinator


async def _insert_task(store: TaskStore) -> Task:
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Rename tClient",
        description="Swap identifier across coordinator package",
    )
    await store.save(task)
    return task


async def test_thread_born_task_posts_resolution(wired):
    store, thread_store, _, coordinator = wired
    thread = await thread_store.create(title="Rename tClient", kind="code+tools")
    task = await _insert_task(store)
    await thread_store.link_task(thread_id=thread.id, task_id=task.id, relation="origin")

    await coordinator.process_pending()

    msgs = await thread_store.list_messages(thread.id)
    assert len(msgs) == 1
    m = msgs[0]
    assert m.role == "assistant"
    assert m.variant == "task-resolved"
    assert m.task_id == task.id
    assert "code-agent" in m.content
    assert "rename tclient" in m.content.lower()
    # Artifact (handler_data) travels with the message as a widget.
    assert len(m.widgets) == 1
    assert "pr_url" in m.widgets[0]


async def test_non_thread_task_stays_silent(wired):
    store, thread_store, _, coordinator = wired
    _ = await thread_store.create(title="Unrelated")  # exists but not linked
    task = await _insert_task(store)

    await coordinator.process_pending()

    # No thread was linked — no messages posted anywhere.
    for t in await thread_store.list():
        assert await thread_store.list_messages(t.id) == []
