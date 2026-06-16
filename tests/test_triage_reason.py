"""Triage declines should surface an actionable reason, not a generic string.

Regression coverage for the "Agent declined task during triage" UX gap: when a
gate agent rejects a task (e.g. a code task with no repo), the failure recorded
on the task should explain *why* and *how to fix it*, instead of a fixed opaque
message. Gates communicate the reason via the documented handler_data trace
(`ctx.store.update_handler_data({"triage_reason": ...})`); the coordinator
surfaces it as the failure error, falling back to the generic message when a
gate declines without leaving a reason.
"""

from forge.agents import AgentContext, AgentRegistry
from forge.agents.code import CodeAgent
from forge.connectors import ConnectorRegistry
from forge.coordinator import Coordinator
from forge.models import Task, TaskSource, TaskStatus, TaskType
from forge.store import TaskStore


class DecliningWithReasonAgent:
    name = "code"
    task_type = "code"
    stages = ["triage", "execute"]
    connectors: list[str] = []

    async def triage(self, task, ctx: AgentContext) -> bool:
        await ctx.store.update_handler_data(
            task.id, {"triage_reason": "needs a repo — set the `repo` field"}
        )
        return False

    async def execute(self, task, ctx):  # pragma: no cover - never reached
        raise AssertionError("execute must not run after a triage decline")


class DecliningSilentlyAgent:
    name = "code"
    task_type = "code"
    stages = ["triage", "execute"]
    connectors: list[str] = []

    async def triage(self, task, ctx: AgentContext) -> bool:
        return False

    async def execute(self, task, ctx):  # pragma: no cover - never reached
        raise AssertionError("execute must not run after a triage decline")


def _coordinator(db, agent) -> tuple[TaskStore, Coordinator]:
    store = TaskStore(db)
    agents = AgentRegistry()
    agents.register(agent)
    coordinator = Coordinator(
        store=store,
        registry=agents,
        connectors=ConnectorRegistry(),
        max_concurrent=2,
    )
    return store, coordinator


async def _queued_code_task(store: TaskStore, repo: str | None = None) -> Task:
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="probe",
        description="probe",
        repo=repo,
    )
    await store.save(task)
    return task


async def test_triage_decline_surfaces_actionable_reason(db):
    store, coordinator = _coordinator(db, DecliningWithReasonAgent())
    task = await _queued_code_task(store)

    await coordinator.process_pending()

    reloaded = await store.get(task.id)
    assert reloaded.status == TaskStatus.FAILED
    assert reloaded.handler_data["error"] == "needs a repo — set the `repo` field"


async def test_triage_decline_without_reason_falls_back_to_generic(db):
    store, coordinator = _coordinator(db, DecliningSilentlyAgent())
    task = await _queued_code_task(store)

    await coordinator.process_pending()

    reloaded = await store.get(task.id)
    assert reloaded.status == TaskStatus.FAILED
    assert reloaded.handler_data["error"] == "Agent declined task during triage"


async def test_code_agent_records_repo_reason_on_decline(db, tmp_path):
    store = TaskStore(db)
    agent = CodeAgent(workspace_dir=str(tmp_path))
    task = await _queued_code_task(store, repo=None)
    ctx = AgentContext(tools=[], store=store, settings=None)

    ok = await agent.triage(task, ctx)

    assert ok is False
    reloaded = await store.get(task.id)
    assert "repo" in reloaded.handler_data["triage_reason"].lower()
