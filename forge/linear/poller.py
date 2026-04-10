import logging
from forge.linear.client import LinearClient
from forge.models import Task, TaskSource, TaskType
from forge.store import TaskStore

logger = logging.getLogger(__name__)

LABEL_TO_TYPE = {
    "research": TaskType.RESEARCH,
    "report": TaskType.REPORT,
    "notebook": TaskType.NOTEBOOK,
    "triage": TaskType.TRIAGE,
}


class LinearPoller:
    def __init__(self, client: LinearClient, store: TaskStore, team_id: str, label: str = "ardent-forge"):
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
            existing = await self._store.find_by_source_id(issue_id)
            if existing is not None:
                continue
            task_type = self._detect_type(issue)
            task = Task.new(
                task_type=task_type,
                source=TaskSource.LINEAR,
                title=issue.get("title", "Untitled"),
                description=issue.get("description", ""),
                source_id=issue_id,
            )
            await self._store.save(task)
            logger.info(f"Created task {task.id} from Linear issue {issue.get('identifier', issue_id)}")
            created += 1
        return created

    def _detect_type(self, issue: dict) -> str:
        labels = [l["name"].lower() for l in issue.get("labels", {}).get("nodes", [])]
        for label, task_type in LABEL_TO_TYPE.items():
            if label in labels:
                return task_type
        return TaskType.CODE
