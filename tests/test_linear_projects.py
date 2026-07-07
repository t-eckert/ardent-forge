import httpx
import respx

from forge.linear.client import LinearClient
from forge.linear.projects import LinearProjectsAPI


@respx.mock
async def test_create_project_returns_id():
    respx.post("https://api.linear.app/graphql").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "projectCreate": {
                        "success": True,
                        "project": {"id": "p1", "url": "https://linear.app/x/project/p1"},
                    }
                }
            },
        )
    )
    client = LinearClient(api_key="k")
    api = LinearProjectsAPI(client)
    project_id, url = await api.create_project(team_id="team-1", name="Phase 0", description="desc")
    assert project_id == "p1"
    assert url.endswith("/p1")


@respx.mock
async def test_create_issue_returns_id_and_identifier():
    respx.post("https://api.linear.app/graphql").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "issueCreate": {
                        "success": True,
                        "issue": {"id": "i1", "identifier": "FORGE-42", "url": "u"},
                    }
                }
            },
        )
    )
    client = LinearClient(api_key="k")
    api = LinearProjectsAPI(client)
    issue_id, identifier, url = await api.create_issue(
        team_id="team-1",
        project_id="p1",
        title="Step 1",
        description="body",
        labels=["devagent"],
        priority=2,
    )
    assert issue_id == "i1"
    assert identifier == "FORGE-42"


@respx.mock
async def test_get_label_id_by_name():
    respx.post("https://api.linear.app/graphql").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"issueLabels": {"nodes": [{"id": "lab1", "name": "devagent"}]}}},
        )
    )
    client = LinearClient(api_key="k")
    api = LinearProjectsAPI(client)
    lid = await api.get_label_id(team_id="team-1", name="devagent")
    assert lid == "lab1"
