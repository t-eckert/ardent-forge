import pytest
from unittest.mock import AsyncMock

from forge.linear.sync import LinearSync
from forge.models import TaskStatus


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get_workflow_states.return_value = [
        {"id": "state-backlog", "name": "Backlog", "type": "backlog"},
        {"id": "state-progress", "name": "In Progress", "type": "started"},
        {"id": "state-done", "name": "Done", "type": "completed"},
        {"id": "state-cancelled", "name": "Cancelled", "type": "cancelled"},
    ]
    return client


@pytest.fixture
async def sync(mock_client):
    s = LinearSync(client=mock_client, team_id="team-1")
    await s.initialize()
    return s


async def test_sync_executing_to_in_progress(sync, mock_client):
    await sync.sync_status("issue-1", TaskStatus.EXECUTING)
    mock_client.update_issue_state.assert_called_once_with("issue-1", "state-progress")


async def test_sync_completed_to_done(sync, mock_client):
    await sync.sync_status("issue-1", TaskStatus.COMPLETED)
    mock_client.update_issue_state.assert_called_once_with("issue-1", "state-done")


async def test_sync_posts_comment_on_completion(sync, mock_client):
    await sync.on_task_completed("issue-1", pr_url="https://github.com/test/pr/1")
    mock_client.add_comment.assert_called_once()
    call_body = mock_client.add_comment.call_args[0][1]
    assert "https://github.com/test/pr/1" in call_body


async def test_sync_posts_comment_on_failure(sync, mock_client):
    await sync.on_task_failed("issue-1", error="Build failed: missing import")
    mock_client.add_comment.assert_called_once()
    call_body = mock_client.add_comment.call_args[0][1]
    assert "Build failed" in call_body


async def test_initialize_caches_states(sync):
    assert sync._state_map["started"] == "state-progress"
    assert sync._state_map["completed"] == "state-done"
