import pytest
from unittest.mock import AsyncMock

from forge.db import Database
from forge.linear.poller import LinearPoller
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
def mock_client():
    return AsyncMock()


@pytest.fixture
def poller(mock_client, store):
    return LinearPoller(client=mock_client, store=store, team_id="team-1", label="ardent-forge")


async def test_poll_creates_tasks(poller, store, mock_client):
    mock_client.get_labeled_issues.return_value = [
        {
            "id": "issue-1",
            "identifier": "AF-1",
            "title": "Fix the bug",
            "description": "Bug in login",
            "labels": {"nodes": [{"name": "ardent-forge"}]},
        },
        {
            "id": "issue-2",
            "identifier": "AF-2",
            "title": "Add feature",
            "description": "New feature",
            "labels": {"nodes": [{"name": "ardent-forge"}, {"name": "research"}]},
        },
    ]
    created = await poller.poll()
    assert created == 2
    all_tasks = await store.list_all()
    assert len(all_tasks) == 2


async def test_poll_skips_existing(poller, store, mock_client):
    mock_client.get_labeled_issues.return_value = [
        {
            "id": "issue-1",
            "identifier": "AF-1",
            "title": "Fix the bug",
            "description": "Already exists",
            "labels": {"nodes": [{"name": "ardent-forge"}]},
        },
    ]
    await poller.poll()
    created = await poller.poll()
    assert created == 0
    all_tasks = await store.list_all()
    assert len(all_tasks) == 1


async def test_poll_detects_task_type_from_labels(poller, store, mock_client):
    mock_client.get_labeled_issues.return_value = [
        {
            "id": "issue-r",
            "identifier": "AF-R",
            "title": "Research topic",
            "description": "Research something",
            "labels": {"nodes": [{"name": "ardent-forge"}, {"name": "research"}]},
        },
    ]
    await poller.poll()
    all_tasks = await store.list_all()
    assert len(all_tasks) == 1
    assert all_tasks[0].type == "code"


async def test_poll_empty(poller, mock_client):
    mock_client.get_labeled_issues.return_value = []
    created = await poller.poll()
    assert created == 0
