"""Coordinator.nudge() wakes the run_loop early so chat-dispatched tasks
don't have to wait the full poll_interval before processing. Critical for
the interactive dispatch loop to feel responsive.
"""

import asyncio


from forge.agents import AgentContext, AgentRegistry
from forge.coordinator import Coordinator
from forge.db import Database
from forge.models import Task, TaskSource
from forge.store import TaskStore


class NoopAgent:
    name = "echo"
    task_type = "echo"
    stages = ["execute"]
    connectors: list[str] = []

    async def execute(self, task, ctx: AgentContext):
        return {"echoed": task.title}


async def test_nudge_wakes_loop_before_poll_interval():
    db = Database(":memory:")
    await db.initialize()
    try:
        store = TaskStore(db)
        agents = AgentRegistry()
        agents.register(NoopAgent())
        coordinator = Coordinator(store=store, registry=agents, max_concurrent=1)

        # Long poll_interval — without a nudge this test would have to wait
        # 30 seconds to see a tick. With nudge it should fire almost instantly.
        loop_task = asyncio.create_task(coordinator.run_loop(poll_interval=30))

        # Wait for the loop to enter its first wait-for-nudge state.
        await asyncio.sleep(0.1)

        # Insert a task and nudge.
        task = Task.new(
            task_type="echo",  # free-string task type (not in TaskType enum)
            source=TaskSource.CHAT,
            title="Nudge me",
            description="immediate",
        )
        await store.save(task)
        coordinator.nudge()

        # Poll for completion with a tight timeout — should be done in well
        # under a second since we skipped the 30s sleep.
        for _ in range(50):
            got = await store.get(task.id)
            if got and got.status.value == "completed":
                break
            await asyncio.sleep(0.05)
        else:
            raise AssertionError("task never completed after nudge")

        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass
    finally:
        await db.close()


async def test_nudge_before_run_loop_is_noop():
    """Calling nudge() before run_loop starts shouldn't raise — the event
    object is created lazily when the loop begins."""
    db = Database(":memory:")
    await db.initialize()
    try:
        store = TaskStore(db)
        agents = AgentRegistry()
        agents.register(NoopAgent())
        coordinator = Coordinator(store=store, registry=agents)
        # Doesn't raise — just a no-op.
        coordinator.nudge()
    finally:
        await db.close()
