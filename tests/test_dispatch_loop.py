"""Phase P₁ — mechanical guarantees for the thread → task → resolution loop.

Complements test_orchestrator_resolution.py. These tests pin down behaviours
that are easy to regress once chat.py grows a dispatch branch (Phase P₂):

 1. A failed task does NOT post a resolution message. (Resolution narration
    is "the agent finished" — failures surface through state, not prose.)
 2. A multi-stage agent (triage → execute → verify → deliver) still posts
    exactly one resolution message, with the aggregated result across stages.
 3. A thread that only *references* a task (relation='reference') does not
    receive a resolution message when the task completes — only the origin
    thread does.
 4. Re-running the coordinator over an already-completed task does not
    double-post.
"""

import pytest

from forge.agents import AgentContext, AgentRegistry
from forge.connectors import ConnectorRegistry
from forge.coordinator import Coordinator
from forge.db import Database
from forge.models import Task, TaskSource, TaskType
from forge.orchestrator import ForgeOrchestrator
from forge.store import TaskStore
from forge.thread_store import ThreadStore


class FailingAgent:
    name = "code-agent"
    task_type = "code"
    stages = ["execute"]
    connectors: list[str] = []

    async def execute(self, task, ctx: AgentContext):
        raise RuntimeError("fake failure inside execute")


class MultiStageAgent:
    name = "plan-agent"
    task_type = "plan"
    stages = ["triage", "execute", "verify", "deliver"]
    connectors: list[str] = []

    async def triage(self, task, ctx):
        return True  # triage returns a pass/fail bool

    async def execute(self, task, ctx):
        return {"plan_md": "# step 1\n# step 2"}

    async def verify(self, task, ctx):
        return True  # verify returns a pass/fail bool

    async def deliver(self, task, ctx):
        return {"delivered_at": "now"}


class PassThroughAgent:
    name = "code-agent"
    task_type = "code"
    stages = ["execute"]
    connectors: list[str] = []

    async def execute(self, task, ctx):
        return {"pr_url": "https://example.com/pr/1"}


def _wire(db: Database, agent) -> tuple[TaskStore, ThreadStore, Coordinator]:
    store = TaskStore(db)
    thread_store = ThreadStore(db)
    agents = AgentRegistry()
    agents.register(agent)
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
    return store, thread_store, coordinator


async def _origin_task(store: TaskStore, thread_store: ThreadStore, title: str, task_type: TaskType):
    thread = await thread_store.create(title=title, kind="code+tools")
    task = Task.new(
        task_type=task_type,
        source=TaskSource.CHAT,
        title=title,
        description="integration fixture",
    )
    await store.save(task)
    await thread_store.link_task(thread_id=thread.id, task_id=task.id, relation="origin")
    return thread, task


async def test_failed_task_does_not_post_resolution(db):
    store, thread_store, coordinator = _wire(db, FailingAgent())
    thread, _ = await _origin_task(store, thread_store, "Rename fails", TaskType.CODE)

    await coordinator.process_pending()

    msgs = await thread_store.list_messages(thread.id)
    assert msgs == [], "failed task should not narrate a resolution"


async def test_multi_stage_aggregates_and_posts_once(db):
    store, thread_store, coordinator = _wire(db, MultiStageAgent())
    thread, task = await _origin_task(store, thread_store, "Plan split", TaskType.PLAN)

    await coordinator.process_pending()

    msgs = await thread_store.list_messages(thread.id)
    assert len(msgs) == 1
    (m,) = msgs
    assert m.variant == "task-resolved"
    assert m.task_id == task.id
    # Widget payload is the aggregated result — execute's output merged with
    # deliver's. (triage/verify return pass/fail bools, not data.)
    (widget,) = m.widgets
    assert "plan_md" in widget
    assert "delivered_at" in widget


async def test_reference_only_thread_gets_no_message(db):
    store, thread_store, coordinator = _wire(db, PassThroughAgent())
    origin, task = await _origin_task(store, thread_store, "Real rename", TaskType.CODE)
    observer = await thread_store.create(title="Peanut gallery")
    await thread_store.link_task(
        thread_id=observer.id, task_id=task.id, relation="referenced"
    )

    await coordinator.process_pending()

    assert len(await thread_store.list_messages(origin.id)) == 1
    assert await thread_store.list_messages(observer.id) == []


async def test_reprocessing_does_not_double_post(db):
    store, thread_store, coordinator = _wire(db, PassThroughAgent())
    thread, _ = await _origin_task(store, thread_store, "Idempotent", TaskType.CODE)

    await coordinator.process_pending()
    await coordinator.process_pending()  # no pending tasks — should be a no-op

    msgs = await thread_store.list_messages(thread.id)
    assert len(msgs) == 1
