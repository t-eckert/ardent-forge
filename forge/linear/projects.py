import logging

from forge.linear.client import LinearClient

logger = logging.getLogger(__name__)


class LinearProjectsAPI:
    def __init__(self, client: LinearClient):
        self._client = client

    async def create_project(
        self, team_id: str, name: str, description: str
    ) -> tuple[str, str]:
        query = """
        mutation ProjectCreate($teamIds: [String!]!, $name: String!, $description: String!) {
            projectCreate(input: { teamIds: $teamIds, name: $name, description: $description }) {
                success
                project { id url }
            }
        }
        """
        result = await self._client._query(
            query, {"teamIds": [team_id], "name": name, "description": description}
        )
        project = result["data"]["projectCreate"]["project"]
        return project["id"], project.get("url", "")

    async def get_label_id(self, team_id: str, name: str) -> str | None:
        query = """
        query Labels($teamId: ID!) {
            issueLabels(filter: { team: { id: { eq: $teamId } } }) {
                nodes { id name }
            }
        }
        """
        try:
            result = await self._client._query(query, {"teamId": team_id})
            nodes = result["data"]["issueLabels"]["nodes"]
        except (KeyError, TypeError):
            return None
        for node in nodes:
            if node["name"].lower() == name.lower():
                return node["id"]
        return None

    async def create_issue(
        self,
        team_id: str,
        project_id: str,
        title: str,
        description: str,
        labels: list[str] | None = None,
        priority: int | None = None,
        label_ids: list[str] | None = None,
    ) -> tuple[str, str, str]:
        query = """
        mutation IssueCreate($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue { id identifier url }
            }
        }
        """
        input_payload: dict = {
            "teamId": team_id,
            "projectId": project_id,
            "title": title,
            "description": description,
        }
        if priority is not None:
            input_payload["priority"] = priority
        resolved_label_ids: list[str] = list(label_ids or [])
        if labels and not resolved_label_ids:
            for label_name in labels:
                lid = await self.get_label_id(team_id, label_name)
                if lid:
                    resolved_label_ids.append(lid)
        if resolved_label_ids:
            input_payload["labelIds"] = resolved_label_ids

        result = await self._client._query(query, {"input": input_payload})
        issue = result["data"]["issueCreate"]["issue"]
        return issue["id"], issue["identifier"], issue.get("url", "")
