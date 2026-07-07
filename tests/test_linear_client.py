import pytest
from unittest.mock import AsyncMock, patch

from forge.linear.client import LinearClient, LinearAPIError


@pytest.fixture
def client():
    return LinearClient(api_key="test-key")


def test_client_init(client):
    assert client._api_key == "test-key"


async def test_query_issues(client):
    mock_response = {
        "data": {
            "issues": {
                "nodes": [
                    {
                        "id": "issue-1",
                        "identifier": "AF-1",
                        "title": "Fix bug",
                        "description": "There is a bug",
                        "state": {"name": "Backlog", "type": "backlog"},
                        "labels": {"nodes": [{"name": "ardent-forge"}]},
                        "assignee": None,
                    }
                ]
            }
        }
    }
    with patch.object(client, "_query", new_callable=AsyncMock, return_value=mock_response):
        issues = await client.get_labeled_issues(team_id="team-1", label="ardent-forge")
        assert len(issues) == 1
        assert issues[0]["identifier"] == "AF-1"


async def test_update_issue_state(client):
    mock_response = {"data": {"issueUpdate": {"success": True}}}
    with patch.object(client, "_query", new_callable=AsyncMock, return_value=mock_response):
        result = await client.update_issue_state("issue-1", "state-id-in-progress")
        assert result is True


async def test_add_comment(client):
    mock_response = {"data": {"commentCreate": {"success": True}}}
    with patch.object(client, "_query", new_callable=AsyncMock, return_value=mock_response):
        result = await client.add_comment("issue-1", "Work started by Ardent Forge")
        assert result is True


async def test_get_workflow_states(client):
    mock_response = {
        "data": {
            "workflowStates": {
                "nodes": [
                    {"id": "state-1", "name": "Backlog", "type": "backlog"},
                    {"id": "state-2", "name": "In Progress", "type": "started"},
                    {"id": "state-3", "name": "Done", "type": "completed"},
                ]
            }
        }
    }
    with patch.object(client, "_query", new_callable=AsyncMock, return_value=mock_response):
        states = await client.get_workflow_states("team-1")
        assert len(states) == 3
        assert states[1]["name"] == "In Progress"


async def test_api_error_raised():
    client = LinearClient(api_key="bad-key")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = AsyncMock()
        mock_resp.json.return_value = {"errors": [{"message": "Auth failed"}]}
        mock_resp.raise_for_status = AsyncMock()
        mock_post.return_value = mock_resp
        with pytest.raises(LinearAPIError, match="Auth failed"):
            await client._query("{ viewer { id } }")
