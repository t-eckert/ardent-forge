import logging
from forge.linear.client import LinearClient
from forge.models import TaskStatus

logger = logging.getLogger(__name__)

STATUS_TO_LINEAR_STATE_TYPE = {
    TaskStatus.QUEUED: "backlog",
    TaskStatus.TRIAGING: "started",
    TaskStatus.EXECUTING: "started",
    TaskStatus.VERIFYING: "started",
    TaskStatus.DELIVERING: "started",
    TaskStatus.COMPLETED: "completed",
    TaskStatus.FAILED: "cancelled",
}


class LinearSync:
    def __init__(self, client: LinearClient, team_id: str):
        self._client = client
        self._team_id = team_id
        self._state_map: dict[str, str] = {}

    async def initialize(self):
        states = await self._client.get_workflow_states(self._team_id)
        for state in states:
            self._state_map[state["type"]] = state["id"]
        logger.info(f"Cached {len(self._state_map)} workflow states")

    async def sync_status(self, issue_id: str, task_status: TaskStatus):
        state_type = STATUS_TO_LINEAR_STATE_TYPE.get(task_status)
        if not state_type:
            return
        state_id = self._state_map.get(state_type)
        if not state_id:
            logger.warning(f"No Linear state found for type '{state_type}'")
            return
        await self._client.update_issue_state(issue_id, state_id)

    async def on_task_completed(self, issue_id: str, pr_url: str | None = None):
        parts = ["Ardent Forge completed this task."]
        if pr_url:
            parts.append(f"\n**PR:** {pr_url}")
        await self._client.add_comment(issue_id, "\n".join(parts))
        await self.sync_status(issue_id, TaskStatus.COMPLETED)

    async def on_task_failed(self, issue_id: str, error: str):
        body = f"Ardent Forge failed on this task.\n\n**Error:**\n```\n{error}\n```"
        await self._client.add_comment(issue_id, body)
