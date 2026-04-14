import pytest

from forge.coordinator import Coordinator
from forge.db import Database
from forge.agents import AgentContext, AgentRegistry
from forge.models import Task, TaskSource, TaskStatus, TaskType
from forge.store import TaskStore


class DataProducingHandler:
    name = "data_test"
    task_type = "data_test"
    stages = ["triage", "execute", "verify", "deliver"]
    connectors: list[str] = []

    async def triage(self, task: Task, ctx: AgentContext) -> bool:
        return True

    async def execute(self, task: Task, ctx: AgentContext) -> dict:
        return {"computed_value": "hello from execute"}

    async def verify(self, task: Task, ctx: AgentContext) -> bool:
        return task.handler_data.get("computed_value") == "hello from execute"

    async def deliver(self, task: Task, ctx: AgentContext) -> dict:
        val = task.handler_data.get("computed_value", "missing")
        return {"status": "delivered", "echo": val}


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
def store(db):
    return TaskStore(db)


@pytest.fixture
def registry():
    reg = AgentRegistry()
    reg.register(DataProducingHandler())
    return reg


@pytest.fixture
def coordinator(store, registry):
    return Coordinator(store=store, registry=registry, max_concurrent=2)


async def test_handler_data_flows_through_pipeline(coordinator, store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Data flow test",
        description="Test handler_data propagation",
    )
    task = task.model_copy(update={"type": "data_test"})
    await store.save(task)

    await coordinator.process_pending()
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.COMPLETED
    assert loaded.result["echo"] == "hello from execute"
