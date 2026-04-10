# Linear Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect Ardent Forge to Linear so it can poll for labeled issues, ingest them as tasks, update issue status as work progresses, and post comments with results.

**Architecture:** A Linear API client using httpx for GraphQL queries/mutations. A poller that runs on a configurable interval, finds unassigned issues labeled `ardent-forge`, and creates internal tasks. Status updates and comments flow back to Linear as tasks progress.

**Tech Stack:** Python 3.13, httpx (async HTTP), Linear GraphQL API

---

## File Structure

```
forge/
├── linear/
│   ├── __init__.py               # Package marker
│   ├── client.py                 # Linear GraphQL client (query, mutate)
│   ├── poller.py                 # Issue polling and task ingestion
│   └── sync.py                   # Status sync (task status → Linear updates)
├── config.py                     # (modify) Add linear_team_id

tests/
├── test_linear_client.py         # Client tests (mocked HTTP)
├── test_linear_poller.py         # Poller tests
└── test_linear_sync.py           # Status sync tests
```

---

### Task 1: Linear GraphQL Client

**Files:**
- Create: `forge/linear/__init__.py`
- Create: `forge/linear/client.py`
- Create: `tests/test_linear_client.py`
- Modify: `forge/config.py` (add `linear_team_id`)

- [ ] **Step 1: Write the failing tests**

`tests/test_linear_client.py`:
```python
import json
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
        assert issues[0]["title"] == "Fix bug"


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
    mock_response = {"errors": [{"message": "Authentication required"}]}

    with patch.object(client, "_query", new_callable=AsyncMock, return_value=mock_response):
        pass  # _query itself raises; tested via direct call

    # Test that _query raises on errors
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = AsyncMock()
        mock_resp.json.return_value = {"errors": [{"message": "Auth failed"}]}
        mock_resp.raise_for_status = AsyncMock()
        mock_post.return_value = mock_resp

        with pytest.raises(LinearAPIError, match="Auth failed"):
            await client._query("{ viewer { id } }")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_linear_client.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Add linear_team_id to config**

In `forge/config.py`, add to the `Settings` class:

```python
    # Linear
    linear_team_id: str = ""
```

- [ ] **Step 4: Write implementation**

`forge/linear/__init__.py`:
```python
```

`forge/linear/client.py`:
```python
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
                headers={
                    "Authorization": self._api_key,
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown error")
                raise LinearAPIError(error_msg)

            return data

    async def get_labeled_issues(self, team_id: str, label: str) -> list[dict]:
        query = """
        query GetIssues($teamId: String!, $label: String!) {
            issues(
                filter: {
                    team: { id: { eq: $teamId } }
                    assignee: { null: true }
                    labels: { name: { eq: $label } }
                    state: { type: { in: ["backlog", "unstarted"] } }
                }
                first: 20
                orderBy: createdAt
            ) {
                nodes {
                    id
                    identifier
                    title
                    description
                    state { name type }
                    labels { nodes { name } }
                    assignee { id name }
                }
            }
        }
        """
        result = await self._query(query, {"teamId": team_id, "label": label})
        return result["data"]["issues"]["nodes"]

    async def update_issue_state(self, issue_id: str, state_id: str) -> bool:
        query = """
        mutation UpdateIssue($issueId: String!, $stateId: String!) {
            issueUpdate(id: $issueId, input: { stateId: $stateId }) {
                success
            }
        }
        """
        result = await self._query(query, {"issueId": issue_id, "stateId": state_id})
        return result["data"]["issueUpdate"]["success"]

    async def add_comment(self, issue_id: str, body: str) -> bool:
        query = """
        mutation AddComment($issueId: String!, $body: String!) {
            commentCreate(input: { issueId: $issueId, body: $body }) {
                success
            }
        }
        """
        result = await self._query(query, {"issueId": issue_id, "body": body})
        return result["data"]["commentCreate"]["success"]

    async def get_workflow_states(self, team_id: str) -> list[dict]:
        query = """
        query GetStates($teamId: String!) {
            workflowStates(filter: { team: { id: { eq: $teamId } } }) {
                nodes {
                    id
                    name
                    type
                }
            }
        }
        """
        result = await self._query(query, {"teamId": team_id})
        return result["data"]["workflowStates"]["nodes"]

    async def assign_to_me(self, issue_id: str, user_id: str) -> bool:
        query = """
        mutation AssignIssue($issueId: String!, $assigneeId: String!) {
            issueUpdate(id: $issueId, input: { assigneeId: $assigneeId }) {
                success
            }
        }
        """
        result = await self._query(query, {"issueId": issue_id, "assigneeId": user_id})
        return result["data"]["issueUpdate"]["success"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_linear_client.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add forge/linear/ forge/config.py tests/test_linear_client.py
git commit -m "feat: add Linear GraphQL client"
```

---

### Task 2: Issue Poller

**Files:**
- Create: `forge/linear/poller.py`
- Create: `tests/test_linear_poller.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_linear_poller.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from forge.db import Database
from forge.linear.poller import LinearPoller
from forge.models import TaskSource, TaskStatus
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
    client = AsyncMock()
    return client


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

    task1 = all_tasks[1]  # Oldest first (list_all is DESC, so index 1)
    assert task1.title == "Fix the bug"
    assert task1.source == TaskSource.LINEAR
    assert task1.source_id == "issue-1"


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

    # First poll creates the task
    await poller.poll()
    # Second poll should skip it
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
    assert all_tasks[0].type == "research"


async def test_poll_empty(poller, mock_client):
    mock_client.get_labeled_issues.return_value = []
    created = await poller.poll()
    assert created == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_linear_poller.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write implementation**

`forge/linear/poller.py`:
```python
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
        """Poll Linear for new issues and create tasks. Returns count of new tasks created."""
        issues = await self._client.get_labeled_issues(self._team_id, self._label)

        if not issues:
            return 0

        created = 0
        for issue in issues:
            issue_id = issue["id"]

            # Check if we already have a task for this issue
            existing = await self._store.find_by_source_id(issue_id)
            if existing is not None:
                continue

            # Detect task type from labels
            task_type = self._detect_type(issue)

            # Detect repo from issue (could be in description or labels)
            repo = self._detect_repo(issue)

            task = Task.new(
                task_type=task_type,
                source=TaskSource.LINEAR,
                title=issue.get("title", "Untitled"),
                description=issue.get("description", ""),
                source_id=issue_id,
                repo=repo,
            )

            await self._store.save(task)
            logger.info(f"Created task {task.id} from Linear issue {issue.get('identifier', issue_id)}")
            created += 1

        return created

    def _detect_type(self, issue: dict) -> str:
        """Detect task type from issue labels."""
        labels = [
            label["name"].lower()
            for label in issue.get("labels", {}).get("nodes", [])
        ]

        for label, task_type in LABEL_TO_TYPE.items():
            if label in labels:
                return task_type

        return TaskType.CODE

    def _detect_repo(self, issue: dict) -> str | None:
        """Try to detect the target repo from the issue.
        For now, returns None — repo can be set in the issue description
        or via a future convention (e.g., a 'repo:' label or field).
        """
        return None
```

- [ ] **Step 4: Add find_by_source_id to store**

In `forge/store.py`, add:

```python
    async def find_by_source_id(self, source_id: str) -> Task | None:
        row = await self._db.fetch_one(
            "SELECT * FROM tasks WHERE source_id = ?", (source_id,)
        )
        if row is None:
            return None
        return Task.from_row(row)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_linear_poller.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add forge/linear/poller.py forge/store.py tests/test_linear_poller.py
git commit -m "feat: add Linear issue poller with task ingestion"
```

---

### Task 3: Status Sync (Task → Linear)

**Files:**
- Create: `forge/linear/sync.py`
- Create: `tests/test_linear_sync.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_linear_sync.py`:
```python
import pytest
from unittest.mock import AsyncMock

from forge.db import Database
from forge.linear.sync import LinearSync
from forge.models import Task, TaskSource, TaskStatus, TaskType
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_linear_sync.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write implementation**

`forge/linear/sync.py`:
```python
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
        """Fetch and cache workflow states from Linear."""
        states = await self._client.get_workflow_states(self._team_id)
        for state in states:
            self._state_map[state["type"]] = state["id"]
        logger.info(f"Cached {len(self._state_map)} workflow states")

    async def sync_status(self, issue_id: str, task_status: TaskStatus):
        """Update the Linear issue state to match the task status."""
        state_type = STATUS_TO_LINEAR_STATE_TYPE.get(task_status)
        if not state_type:
            return

        state_id = self._state_map.get(state_type)
        if not state_id:
            logger.warning(f"No Linear state found for type '{state_type}'")
            return

        await self._client.update_issue_state(issue_id, state_id)

    async def on_task_completed(self, issue_id: str, pr_url: str | None = None):
        """Post a completion comment to the Linear issue."""
        parts = ["Ardent Forge completed this task."]
        if pr_url:
            parts.append(f"\n**PR:** {pr_url}")

        await self._client.add_comment(issue_id, "\n".join(parts))
        await self.sync_status(issue_id, TaskStatus.COMPLETED)

    async def on_task_failed(self, issue_id: str, error: str):
        """Post a failure comment to the Linear issue."""
        body = f"Ardent Forge failed on this task.\n\n**Error:**\n```\n{error}\n```"
        await self._client.add_comment(issue_id, body)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_linear_sync.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add forge/linear/sync.py tests/test_linear_sync.py
git commit -m "feat: add Linear status sync (task status → Linear updates)"
```

---

### Task 4: Wire Linear Into Coordinator Lifespan

**Files:**
- Modify: `forge/main.py`
- Modify: `forge/coordinator.py`
- Create: `tests/test_linear_integration.py`

- [ ] **Step 1: Write the failing test**

`tests/test_linear_integration.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch

from forge.coordinator import Coordinator
from forge.db import Database
from forge.handlers import HandlerRegistry
from forge.handlers.echo import EchoHandler
from forge.linear.poller import LinearPoller
from forge.models import Task, TaskSource, TaskStatus, TaskType
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
    reg = HandlerRegistry()
    reg.register(EchoHandler())
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
    # But echo handler won't match "code" type — task will fail
    # That's fine, we're testing the ingestion flow
    await coordinator.tick()

    all_tasks = await store.list_all()
    assert len(all_tasks) == 1
    assert all_tasks[0].source == TaskSource.LINEAR
    assert all_tasks[0].source_id == "linear-issue-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_linear_integration.py -v`
Expected: FAIL — Coordinator doesn't accept a `poller` parameter yet

- [ ] **Step 3: Update Coordinator to accept optional poller**

In `forge/coordinator.py`, update `__init__` to accept an optional poller:

```python
from forge.linear.poller import LinearPoller

class Coordinator:
    def __init__(self, store: TaskStore, registry: HandlerRegistry, max_concurrent: int = 2, poller: "LinearPoller | None" = None):
        self._store = store
        self._registry = registry
        self._max_concurrent = max_concurrent
        self._poller = poller
```

Update `tick()` to poll before processing:

```python
    async def tick(self) -> int:
        if self._poller:
            try:
                created = await self._poller.poll()
                if created > 0:
                    logger.info(f"Ingested {created} tasks from Linear")
            except Exception:
                logger.exception("Error polling Linear")
        return await self.process_pending()
```

Use a string annotation or `TYPE_CHECKING` import to avoid circular imports if needed.

- [ ] **Step 4: Update main.py lifespan to create poller when linear is configured**

In `forge/main.py` lifespan, after creating the coordinator:

```python
        poller = None
        if settings.linear_api_key and settings.linear_team_id:
            from forge.linear.client import LinearClient
            from forge.linear.poller import LinearPoller
            linear_client = LinearClient(api_key=settings.linear_api_key)
            poller = LinearPoller(
                client=linear_client,
                store=store,
                team_id=settings.linear_team_id,
            )

        coordinator = Coordinator(
            store=store,
            registry=registry,
            max_concurrent=settings.max_concurrent_tasks,
            poller=poller,
        )
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add forge/coordinator.py forge/main.py tests/test_linear_integration.py
git commit -m "feat: wire Linear poller into coordinator lifecycle"
```

---

### Task 5: Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run the complete test suite**

```bash
uv run pytest -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 2: Verify module structure**

```bash
find forge/linear -name "*.py" | sort
```

Expected:
```
forge/linear/__init__.py
forge/linear/client.py
forge/linear/poller.py
forge/linear/sync.py
```
