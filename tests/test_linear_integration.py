import pytest
from unittest.mock import AsyncMock

from forge.coordinator import Coordinator
from forge.db import Database
from forge.agents import AgentRegistry
from forge.agents.echo import EchoAgent
from forge.linear.poller import LinearPoller
from forge.models import TaskSource
from forge.store import TaskStore


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
    reg.register(EchoAgent())
    return reg


async def test_coordinator_with_poller(store, registry):
    mock_client = AsyncMock()
    mock_client.get_labeled_issues.return_value = [
        {
            "id": "linear-issue-1",
            "identifier": "AF-1",
            "title": "Echo task from Linear",
            "description": "Test Linear ingestion",
            "labels": {"nodes": [{"name": "ardent-forge"}]},
        }
    ]

    poller = LinearPoller(client=mock_client, store=store, team_id="team-1")
    coordinator = Coordinator(store=store, registry=registry, max_concurrent=2, poller=poller)

    # Tick should poll Linear, create task, then process it
    await coordinator.tick()

    all_tasks = await store.list_all()
    assert len(all_tasks) == 1
    assert all_tasks[0].source == TaskSource.LINEAR
    assert all_tasks[0].source_id == "linear-issue-1"
