import httpx
import logging

logger = logging.getLogger(__name__)
LINEAR_API_URL = "https://api.linear.app/graphql"


class LinearAPIError(Exception):
    pass


class LinearClient:
    def __init__(self, api_key: str):
        self._api_key = api_key

    async def _query(self, query: str, variables: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                LINEAR_API_URL,
                json={"query": query, "variables": variables or {}},
                headers={"Authorization": self._api_key, "Content-Type": "application/json"},
            )
            # raise_for_status and json may be awaitable in test mocks
            raise_result = response.raise_for_status()
            if hasattr(raise_result, "__await__"):
                await raise_result
            json_result = response.json()
            if hasattr(json_result, "__await__"):
                data = await json_result
            else:
                data = json_result
            if "errors" in data:
                raise LinearAPIError(data["errors"][0].get("message", "Unknown error"))
            return data

    async def get_labeled_issues(self, team_id: str, label: str) -> list[dict]:
        query = """
        query GetIssues($teamId: ID!, $label: String!) {
            issues(filter: { team: { id: { eq: $teamId } }, assignee: { null: true }, labels: { name: { eq: $label } }, state: { type: { in: ["backlog", "unstarted"] } } }, first: 20, orderBy: createdAt) {
                nodes { id identifier title description state { name type } labels { nodes { name } } assignee { id name } }
            }
        }
        """
        result = await self._query(query, {"teamId": team_id, "label": label})
        return result["data"]["issues"]["nodes"]

    async def update_issue_state(self, issue_id: str, state_id: str) -> bool:
        query = """
        mutation UpdateIssue($issueId: ID!, $stateId: ID!) {
            issueUpdate(id: $issueId, input: { stateId: $stateId }) { success }
        }
        """
        result = await self._query(query, {"issueId": issue_id, "stateId": state_id})
        return result["data"]["issueUpdate"]["success"]

    async def add_comment(self, issue_id: str, body: str) -> bool:
        query = """
        mutation AddComment($issueId: ID!, $body: String!) {
            commentCreate(input: { issueId: $issueId, body: $body }) { success }
        }
        """
        result = await self._query(query, {"issueId": issue_id, "body": body})
        return result["data"]["commentCreate"]["success"]

    async def get_workflow_states(self, team_id: str) -> list[dict]:
        query = """
        query GetStates($teamId: ID!) {
            workflowStates(filter: { team: { id: { eq: $teamId } } }) { nodes { id name type } }
        }
        """
        result = await self._query(query, {"teamId": team_id})
        return result["data"]["workflowStates"]["nodes"]

    async def assign_to_me(self, issue_id: str, user_id: str) -> bool:
        query = """
        mutation AssignIssue($issueId: ID!, $assigneeId: ID!) {
            issueUpdate(id: $issueId, input: { assigneeId: $assigneeId }) { success }
        }
        """
        result = await self._query(query, {"issueId": issue_id, "assigneeId": user_id})
        return result["data"]["issueUpdate"]["success"]
