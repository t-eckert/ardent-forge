import logging
import re

from forge.linear.client import LinearClient
from forge.models import Task, TaskSource, TaskType
from forge.store import TaskStore

logger = logging.getLogger(__name__)

LABEL_TO_TYPE = {
    "claude": TaskType.CODE,
}

_REPO_RE = re.compile(r"(?:^|\n)\s*\*{0,2}[Rr]epo:?\*{0,2}\s*([^\s\n]+)", re.MULTILINE)


class LinearPoller:
    def __init__(
        self,
        client: LinearClient,
        store: TaskStore,
        team_id: str,
        label: str = "ardent-forge",
    ):
        self._client = client
        self._store = store
        self._team_id = team_id
        self._label = label

    async def poll(self) -> int:
        issues = await self._client.get_labeled_issues(self._team_id, self._label)
        if not issues:
            return 0
        created = 0
        for issue in issues:
            issue_id = issue["id"]
            if await self._store.find_by_source_id(issue_id) is not None:
                continue
            task_type = self._detect_type(issue)
            repo = self._parse_repo(issue.get("description", "")) if task_type == TaskType.CODE else None
            task = Task.new(
                task_type=task_type,
                source=TaskSource.LINEAR,
                title=issue.get("title", "Untitled"),
                description=self._build_description(issue),
                source_id=issue_id,
                repo=repo,
            )
            await self._store.save(task)
            logger.info(
                "Created %s task %s from Linear issue %s (repo=%r)",
                task_type,
                task.id,
                issue.get("identifier", issue_id),
                repo,
            )
            created += 1
        return created

    async def post_result(self, task: Task) -> None:
        """Post a PR link comment back to the originating Linear issue."""
        if task.source != TaskSource.LINEAR or not task.source_id:
            return
        result = task.result or {}
        pr_url = result.get("pr_url") or task.handler_data.get("pr_url", "")
        if not pr_url or pr_url.startswith("PR creation failed"):
            return
        body = f"Ardent Forge completed this task.\n\n**PR:** {pr_url}"
        await self._client.add_comment(task.source_id, body)
        logger.info("Posted result comment to Linear issue %s", task.source_id)

    def _detect_type(self, issue: dict) -> TaskType:
        labels = [l["name"].lower() for l in issue.get("labels", {}).get("nodes", [])]
        for label, task_type in LABEL_TO_TYPE.items():
            if label in labels:
                return task_type
        return TaskType.CODE

    def _parse_repo(self, description: str) -> str | None:
        """Extract `Repo: owner/name` from issue description."""
        m = _REPO_RE.search(description or "")
        return m.group(1) if m else None

    def _build_description(self, issue: dict) -> str:
        """Build a rich task description from issue fields."""
        parts = [issue.get("description", "").strip()]
        identifier = issue.get("identifier", "")
        if identifier:
            parts.append(f"\n\nLinear: {identifier}")
        return "\n".join(p for p in parts if p)
