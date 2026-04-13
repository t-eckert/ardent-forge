# Forge Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core Ardent Forge Python application — SQLite persistence, task state machine, coordinator loop, and FastAPI API — so that tasks can be created, queued, executed by handlers, and tracked.

**Architecture:** A monolithic FastAPI application using SQLite for all state. The coordinator runs as an async background task that dequeues tasks and dispatches them to handlers. Handlers implement a common protocol (`triage → execute → verify → deliver`). State transitions persist immediately to SQLite. The app is developed and tested locally before deployment.

**Tech Stack:** Python 3.13, uv, FastAPI, uvicorn, SQLite (aiosqlite), Pydantic, pytest

**Reference:** The galley devagent (`~/Repos/github.com/t-eckert/galley/galley-devagent/`) is the architectural ancestor. This plan adapts its patterns (polling loop, handler dispatch, audit logging) into a more general task-type-agnostic coordinator.

---

## File Structure

```
ardent-forge/
├── pyproject.toml                    # Project config, dependencies, scripts
├── forge/
│   ├── __init__.py
│   ├── main.py                       # FastAPI app, lifespan, startup/shutdown
│   ├── config.py                     # Pydantic Settings (env vars)
│   ├── db.py                         # SQLite connection, schema init, migrations
│   ├── models.py                     # Pydantic models (Task, Schedule, ChatMessage)
│   ├── state.py                      # Task state machine (transitions, validation)
│   ├── coordinator.py                # Async coordinator loop (dequeue, dispatch)
│   ├── handlers/
│   │   ├── __init__.py               # Handler registry, protocol definition
│   │   └── echo.py                   # Echo handler (test/placeholder handler)
│   └── api/
│       ├── __init__.py
│       ├── tasks.py                  # Task CRUD + status endpoints
│       └── health.py                 # Health check endpoint
└── tests/
    ├── __init__.py
    ├── conftest.py                   # Shared fixtures (in-memory SQLite, test client)
    ├── test_db.py                    # Database schema and operations
    ├── test_state.py                 # State machine transitions
    ├── test_coordinator.py           # Coordinator loop behavior
    ├── test_handlers.py              # Handler protocol and echo handler
    └── test_api.py                   # API endpoint tests
```

---

### Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `forge/__init__.py`
- Create: `forge/main.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Initialize uv project**

```bash
cd /Users/thomaseckert/Repos/github.com/t-eckert/ardent-forge
uv init --lib --name ardent-forge
```

- [ ] **Step 2: Replace pyproject.toml with project config**

```toml
[project]
name = "ardent-forge"
version = "0.1.0"
description = "Agentic development and life-coordination system"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "aiosqlite>=0.20",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "ulid-py>=1.1",
]

[project.scripts]
forge = "forge.main:run"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "httpx>=0.28",
]
```

- [ ] **Step 3: Create forge/__init__.py**

```python
```

(Empty file — package marker only.)

- [ ] **Step 4: Create minimal forge/main.py**

```python
import uvicorn
from fastapi import FastAPI

app = FastAPI(title="Ardent Forge")


@app.get("/health")
async def health():
    return {"status": "ok"}


def run():
    uvicorn.run("forge.main:app", host="0.0.0.0", port=7030, reload=True)
```

- [ ] **Step 5: Create tests/__init__.py and tests/conftest.py**

`tests/__init__.py`:
```python
```

`tests/conftest.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient

from forge.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

- [ ] **Step 6: Install dependencies**

```bash
uv sync
```

- [ ] **Step 7: Verify setup**

Run: `uv run pytest --co -q`
Expected: "no tests ran" (collected 0)

Run: `uv run forge`
Expected: Uvicorn starts on port 7030, curl localhost:7030/health returns `{"status":"ok"}`

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock forge/ tests/
git commit -m "feat: initialize project with FastAPI skeleton"
```

---

### Task 2: Configuration

**Files:**
- Create: `forge/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from forge.config import Settings


def test_default_settings():
    settings = Settings(anthropic_api_key="test-key", github_token="test-token")
    assert settings.db_path == "forge.db"
    assert settings.poll_interval_seconds == 300
    assert settings.max_concurrent_tasks == 2
    assert settings.host == "0.0.0.0"
    assert settings.port == 7030


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("FORGE_DB_PATH", "/tmp/test.db")
    monkeypatch.setenv("FORGE_POLL_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("FORGE_ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("FORGE_GITHUB_TOKEN", "ghp-test")
    settings = Settings()
    assert settings.db_path == "/tmp/test.db"
    assert settings.poll_interval_seconds == 60
    assert settings.anthropic_api_key == "sk-test"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

- [ ] **Step 3: Write implementation**

`forge/config.py`:
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "FORGE_"}

    # Database
    db_path: str = "forge.db"

    # Coordinator
    poll_interval_seconds: int = 300
    max_concurrent_tasks: int = 2

    # Server
    host: str = "0.0.0.0"
    port: int = 7030

    # API Keys
    anthropic_api_key: str = ""
    github_token: str = ""
    linear_api_key: str = ""

    # Repos
    workspace_dir: str = "/var/lib/ardent-forge/repos"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add forge/config.py tests/test_config.py
git commit -m "feat: add configuration with pydantic-settings"
```

---

### Task 3: Database Schema and Operations

**Files:**
- Create: `forge/db.py`
- Create: `tests/test_db.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add database fixture to conftest.py**

Replace `tests/conftest.py` with:
```python
import pytest
from httpx import ASGITransport, AsyncClient

from forge.db import Database


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def client(db):
    from forge.main import create_app

    app = create_app(db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

- [ ] **Step 2: Write the failing tests**

`tests/test_db.py`:
```python
import pytest

from forge.db import Database


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.initialize()
    yield database
    await database.close()


async def test_initialize_creates_tables(db: Database):
    tables = await db.fetch_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    table_names = [row["name"] for row in tables]
    assert "tasks" in table_names
    assert "task_logs" in table_names
    assert "chat_messages" in table_names
    assert "schedules" in table_names


async def test_insert_and_fetch_task(db: Database):
    await db.execute(
        """INSERT INTO tasks (id, type, status, source, title, description, handler_data, retries, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
        ("01TASK001", "code", "queued", "chat", "Test task", "A test", "{}", 0),
    )
    row = await db.fetch_one("SELECT * FROM tasks WHERE id = ?", ("01TASK001",))
    assert row is not None
    assert row["title"] == "Test task"
    assert row["status"] == "queued"
    assert row["type"] == "code"


async def test_update_task_status(db: Database):
    await db.execute(
        """INSERT INTO tasks (id, type, status, source, title, description, handler_data, retries, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
        ("01TASK002", "code", "queued", "chat", "Update me", "Test", "{}", 0),
    )
    await db.execute(
        "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE id = ?",
        ("executing", "01TASK002"),
    )
    row = await db.fetch_one("SELECT status FROM tasks WHERE id = ?", ("01TASK002",))
    assert row["status"] == "executing"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 4: Write implementation**

`forge/db.py`:
```python
import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    source TEXT NOT NULL,
    source_id TEXT,
    repo TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    handler_data TEXT NOT NULL DEFAULT '{}',
    result TEXT,
    retries INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS task_logs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    task_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    cron_expr TEXT NOT NULL,
    task_type TEXT NOT NULL,
    task_template TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1,
    last_run TEXT,
    next_run TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str):
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self):
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        assert self._conn is not None
        cursor = await self._conn.execute(sql, params)
        await self._conn.commit()
        return cursor

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        assert self._conn is not None
        cursor = await self._conn.execute(sql, params)
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        assert self._conn is not None
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_db.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add forge/db.py tests/test_db.py tests/conftest.py
git commit -m "feat: add SQLite database layer with schema"
```

---

### Task 4: Pydantic Models

**Files:**
- Create: `forge/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_models.py`:
```python
from forge.models import Task, TaskStatus, TaskType, TaskSource


def test_create_task():
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Fix the bug",
        description="There is a bug in main.py",
    )
    assert task.status == TaskStatus.QUEUED
    assert task.type == TaskType.CODE
    assert task.source == TaskSource.CHAT
    assert task.retries == 0
    assert task.id is not None
    assert len(task.id) > 0


def test_create_task_with_repo():
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.LINEAR,
        title="Add feature",
        description="New feature",
        repo="t-eckert/ardent-forge",
        source_id="LIN-123",
    )
    assert task.repo == "t-eckert/ardent-forge"
    assert task.source_id == "LIN-123"


def test_task_to_row_and_back():
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Roundtrip",
        description="Test serialization",
    )
    row = task.to_row()
    restored = Task.from_row(row)
    assert restored.id == task.id
    assert restored.title == task.title
    assert restored.status == task.status
    assert restored.handler_data == task.handler_data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write implementation**

`forge/models.py`:
```python
import json
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field
from ulid import ULID


class TaskStatus(StrEnum):
    QUEUED = "queued"
    TRIAGING = "triaging"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    DELIVERING = "delivering"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(StrEnum):
    CODE = "code"
    RESEARCH = "research"
    REPORT = "report"
    NOTEBOOK = "notebook"
    TRIAGE = "triage"


class TaskSource(StrEnum):
    LINEAR = "linear"
    CHAT = "chat"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"


class Task(BaseModel):
    id: str
    type: TaskType
    status: TaskStatus
    source: TaskSource
    source_id: str | None = None
    repo: str | None = None
    title: str
    description: str
    handler_data: dict = Field(default_factory=dict)
    result: dict | None = None
    retries: int = 0
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def new(
        cls,
        task_type: TaskType,
        source: TaskSource,
        title: str,
        description: str,
        repo: str | None = None,
        source_id: str | None = None,
    ) -> "Task":
        now = datetime.now(timezone.utc)
        return cls(
            id=str(ULID()),
            type=task_type,
            status=TaskStatus.QUEUED,
            source=source,
            source_id=source_id,
            repo=repo,
            title=title,
            description=description,
            created_at=now,
            updated_at=now,
        )

    def to_row(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "status": self.status.value,
            "source": self.source.value,
            "source_id": self.source_id,
            "repo": self.repo,
            "title": self.title,
            "description": self.description,
            "handler_data": json.dumps(self.handler_data),
            "result": json.dumps(self.result) if self.result else None,
            "retries": self.retries,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_row(cls, row: dict) -> "Task":
        return cls(
            id=row["id"],
            type=TaskType(row["type"]),
            status=TaskStatus(row["status"]),
            source=TaskSource(row["source"]),
            source_id=row.get("source_id"),
            repo=row.get("repo"),
            title=row["title"],
            description=row["description"],
            handler_data=json.loads(row["handler_data"]) if row["handler_data"] else {},
            result=json.loads(row["result"]) if row.get("result") else None,
            retries=row["retries"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add forge/models.py tests/test_models.py
git commit -m "feat: add Pydantic task models with serialization"
```

---

### Task 5: Task State Machine

**Files:**
- Create: `forge/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_state.py`:
```python
import pytest

from forge.models import TaskStatus
from forge.state import InvalidTransition, transition


def test_valid_transitions():
    assert transition(TaskStatus.QUEUED, TaskStatus.TRIAGING) == TaskStatus.TRIAGING
    assert transition(TaskStatus.TRIAGING, TaskStatus.EXECUTING) == TaskStatus.EXECUTING
    assert transition(TaskStatus.EXECUTING, TaskStatus.VERIFYING) == TaskStatus.VERIFYING
    assert transition(TaskStatus.VERIFYING, TaskStatus.DELIVERING) == TaskStatus.DELIVERING
    assert transition(TaskStatus.DELIVERING, TaskStatus.COMPLETED) == TaskStatus.COMPLETED


def test_any_active_state_can_fail():
    for status in [TaskStatus.TRIAGING, TaskStatus.EXECUTING, TaskStatus.VERIFYING, TaskStatus.DELIVERING]:
        assert transition(status, TaskStatus.FAILED) == TaskStatus.FAILED


def test_queued_can_skip_to_executing():
    assert transition(TaskStatus.QUEUED, TaskStatus.EXECUTING) == TaskStatus.EXECUTING


def test_failed_can_retry_to_queued():
    assert transition(TaskStatus.FAILED, TaskStatus.QUEUED) == TaskStatus.QUEUED


def test_invalid_transition_raises():
    with pytest.raises(InvalidTransition):
        transition(TaskStatus.COMPLETED, TaskStatus.EXECUTING)


def test_completed_is_terminal():
    with pytest.raises(InvalidTransition):
        transition(TaskStatus.COMPLETED, TaskStatus.QUEUED)


def test_queued_cannot_complete_directly():
    with pytest.raises(InvalidTransition):
        transition(TaskStatus.QUEUED, TaskStatus.COMPLETED)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_state.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write implementation**

`forge/state.py`:
```python
from forge.models import TaskStatus

VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.QUEUED: {TaskStatus.TRIAGING, TaskStatus.EXECUTING},
    TaskStatus.TRIAGING: {TaskStatus.EXECUTING, TaskStatus.FAILED},
    TaskStatus.EXECUTING: {TaskStatus.VERIFYING, TaskStatus.FAILED},
    TaskStatus.VERIFYING: {TaskStatus.DELIVERING, TaskStatus.FAILED},
    TaskStatus.DELIVERING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: {TaskStatus.QUEUED},
}


class InvalidTransition(Exception):
    def __init__(self, from_status: TaskStatus, to_status: TaskStatus):
        super().__init__(f"Cannot transition from {from_status} to {to_status}")
        self.from_status = from_status
        self.to_status = to_status


def transition(current: TaskStatus, target: TaskStatus) -> TaskStatus:
    if target not in VALID_TRANSITIONS[current]:
        raise InvalidTransition(current, target)
    return target
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_state.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add forge/state.py tests/test_state.py
git commit -m "feat: add task state machine with transition validation"
```

---

### Task 6: Handler Protocol and Echo Handler

**Files:**
- Create: `forge/handlers/__init__.py`
- Create: `forge/handlers/echo.py`
- Create: `tests/test_handlers.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_handlers.py`:
```python
import pytest

from forge.handlers import HandlerRegistry
from forge.handlers.echo import EchoHandler
from forge.models import Task, TaskSource, TaskType


@pytest.fixture
def task():
    return Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Echo test",
        description="Test the echo handler",
    )


@pytest.fixture
def registry():
    reg = HandlerRegistry()
    reg.register(EchoHandler())
    return reg


async def test_echo_handler_triage(task):
    handler = EchoHandler()
    result = await handler.triage(task)
    assert result is True


async def test_echo_handler_execute(task):
    handler = EchoHandler()
    result = await handler.execute(task)
    assert "echo" in result["message"].lower()


async def test_echo_handler_verify(task):
    handler = EchoHandler()
    result = await handler.verify(task)
    assert result is True


async def test_echo_handler_deliver(task):
    handler = EchoHandler()
    result = await handler.deliver(task)
    assert "delivered" in result["status"]


async def test_registry_finds_handler(registry, task):
    handler = registry.get("echo")
    assert handler is not None
    assert handler.task_type == "echo"


async def test_registry_returns_none_for_unknown(registry):
    handler = registry.get("nonexistent")
    assert handler is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_handlers.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write handler protocol and registry**

`forge/handlers/__init__.py`:
```python
from typing import Protocol

from forge.models import Task


class TaskHandler(Protocol):
    task_type: str

    async def triage(self, task: Task) -> bool: ...
    async def execute(self, task: Task) -> dict: ...
    async def verify(self, task: Task) -> bool: ...
    async def deliver(self, task: Task) -> dict: ...


class HandlerRegistry:
    def __init__(self):
        self._handlers: dict[str, TaskHandler] = {}

    def register(self, handler: TaskHandler):
        self._handlers[handler.task_type] = handler

    def get(self, task_type: str) -> TaskHandler | None:
        return self._handlers.get(task_type)
```

- [ ] **Step 4: Write echo handler**

`forge/handlers/echo.py`:
```python
from forge.models import Task


class EchoHandler:
    task_type: str = "echo"

    async def triage(self, task: Task) -> bool:
        return True

    async def execute(self, task: Task) -> dict:
        return {"message": f"Echo: {task.title}"}

    async def verify(self, task: Task) -> bool:
        return True

    async def deliver(self, task: Task) -> dict:
        return {"status": "delivered", "title": task.title}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_handlers.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add forge/handlers/ tests/test_handlers.py
git commit -m "feat: add handler protocol, registry, and echo handler"
```

---

### Task 7: Task Store (Database CRUD for Tasks)

**Files:**
- Create: `forge/store.py`
- Create: `tests/test_store.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_store.py`:
```python
import pytest

from forge.db import Database
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


async def test_save_and_get_task(store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Save me",
        description="Test persistence",
    )
    await store.save(task)
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.id == task.id
    assert loaded.title == "Save me"


async def test_get_nonexistent_returns_none(store):
    result = await store.get("nonexistent-id")
    assert result is None


async def test_update_status(store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Update me",
        description="Test status update",
    )
    await store.save(task)
    await store.update_status(task.id, TaskStatus.EXECUTING)
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.EXECUTING


async def test_list_by_status(store):
    for i in range(3):
        task = Task.new(
            task_type=TaskType.CODE,
            source=TaskSource.CHAT,
            title=f"Task {i}",
            description="Queued task",
        )
        await store.save(task)

    executing_task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Executing",
        description="Running",
    )
    await store.save(executing_task)
    await store.update_status(executing_task.id, TaskStatus.EXECUTING)

    queued = await store.list_by_status(TaskStatus.QUEUED)
    assert len(queued) == 3

    executing = await store.list_by_status(TaskStatus.EXECUTING)
    assert len(executing) == 1


async def test_list_pending_returns_queued_oldest_first(store):
    tasks = []
    for i in range(3):
        task = Task.new(
            task_type=TaskType.CODE,
            source=TaskSource.CHAT,
            title=f"Task {i}",
            description=f"Pending {i}",
        )
        await store.save(task)
        tasks.append(task)

    pending = await store.list_pending(limit=2)
    assert len(pending) == 2
    assert pending[0].title == "Task 0"
    assert pending[1].title == "Task 1"


async def test_mark_completed(store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Complete me",
        description="Test completion",
    )
    await store.save(task)
    result = {"pr_url": "https://github.com/test/pr/1"}
    await store.mark_completed(task.id, result)
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.COMPLETED
    assert loaded.result == result
    assert loaded.completed_at is not None


async def test_mark_failed(store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Fail me",
        description="Test failure",
    )
    await store.save(task)
    await store.mark_failed(task.id, error="Something broke")
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.FAILED
    assert loaded.handler_data["error"] == "Something broke"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_store.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write implementation**

`forge/store.py`:
```python
import json
from datetime import datetime, timezone

from forge.db import Database
from forge.models import Task, TaskStatus


class TaskStore:
    def __init__(self, db: Database):
        self._db = db

    async def save(self, task: Task):
        row = task.to_row()
        columns = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        await self._db.execute(
            f"INSERT INTO tasks ({columns}) VALUES ({placeholders})",
            tuple(row.values()),
        )

    async def get(self, task_id: str) -> Task | None:
        row = await self._db.fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if row is None:
            return None
        return Task.from_row(row)

    async def update_status(self, task_id: str, status: TaskStatus):
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, now, task_id),
        )

    async def list_by_status(self, status: TaskStatus) -> list[Task]:
        rows = await self._db.fetch_all(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at ASC",
            (status.value,),
        )
        return [Task.from_row(row) for row in rows]

    async def list_pending(self, limit: int = 10) -> list[Task]:
        rows = await self._db.fetch_all(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at ASC LIMIT ?",
            (TaskStatus.QUEUED.value, limit),
        )
        return [Task.from_row(row) for row in rows]

    async def mark_completed(self, task_id: str, result: dict):
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "UPDATE tasks SET status = ?, result = ?, completed_at = ?, updated_at = ? WHERE id = ?",
            (TaskStatus.COMPLETED.value, json.dumps(result), now, now, task_id),
        )

    async def mark_failed(self, task_id: str, error: str):
        now = datetime.now(timezone.utc).isoformat()
        task = await self.get(task_id)
        if task is None:
            return
        handler_data = task.handler_data
        handler_data["error"] = error
        await self._db.execute(
            "UPDATE tasks SET status = ?, handler_data = ?, updated_at = ? WHERE id = ?",
            (TaskStatus.FAILED.value, json.dumps(handler_data), now, task_id),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_store.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add forge/store.py tests/test_store.py
git commit -m "feat: add task store with CRUD operations"
```

---

### Task 8: Coordinator Loop

**Files:**
- Create: `forge/coordinator.py`
- Create: `tests/test_coordinator.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_coordinator.py`:
```python
import asyncio

import pytest

from forge.coordinator import Coordinator
from forge.db import Database
from forge.handlers import HandlerRegistry
from forge.handlers.echo import EchoHandler
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


@pytest.fixture
def coordinator(store, registry):
    return Coordinator(store=store, registry=registry, max_concurrent=2)


async def test_process_single_task(coordinator, store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Process me",
        description="Test processing",
    )
    # Echo handler is registered for "echo" type, not "code"
    # So let's make an echo-typed task
    task.type = TaskType.CODE  # Will not find handler
    await store.save(task)

    # No handler for "code" yet — task should fail
    await coordinator.process_pending()
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.FAILED


async def test_process_echo_task(coordinator, store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Echo me",
        description="Test echo",
    )
    # Override type to match echo handler
    task = task.model_copy(update={"type": "echo"})
    await store.save(task)

    await coordinator.process_pending()
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.COMPLETED
    assert loaded.result is not None


async def test_respects_max_concurrent(coordinator, store):
    tasks = []
    for i in range(5):
        task = Task.new(
            task_type=TaskType.CODE,
            source=TaskSource.CHAT,
            title=f"Task {i}",
            description=f"Concurrent {i}",
        )
        task = task.model_copy(update={"type": "echo"})
        await store.save(task)
        tasks.append(task)

    await coordinator.process_pending()

    completed = await store.list_by_status(TaskStatus.COMPLETED)
    # Should process up to max_concurrent (2) per cycle
    assert len(completed) == 2


async def test_coordinator_tick_processes_and_returns(coordinator, store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Tick test",
        description="Test tick",
    )
    task = task.model_copy(update={"type": "echo"})
    await store.save(task)

    processed = await coordinator.tick()
    assert processed == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_coordinator.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write implementation**

`forge/coordinator.py`:
```python
import asyncio
import logging

from forge.handlers import HandlerRegistry
from forge.models import TaskStatus
from forge.store import TaskStore

logger = logging.getLogger(__name__)


class Coordinator:
    def __init__(self, store: TaskStore, registry: HandlerRegistry, max_concurrent: int = 2):
        self._store = store
        self._registry = registry
        self._max_concurrent = max_concurrent

    async def tick(self) -> int:
        """Run one cycle: dequeue pending tasks, process them, return count processed."""
        return await self.process_pending()

    async def process_pending(self) -> int:
        pending = await self._store.list_pending(limit=self._max_concurrent)
        if not pending:
            return 0

        tasks_processed = 0
        for task in pending:
            handler = self._registry.get(task.type)
            if handler is None:
                logger.warning(f"No handler for task type '{task.type}', failing task {task.id}")
                await self._store.mark_failed(task.id, error=f"No handler registered for type '{task.type}'")
                tasks_processed += 1
                continue

            try:
                await self._store.update_status(task.id, TaskStatus.TRIAGING)
                can_handle = await handler.triage(task)
                if not can_handle:
                    await self._store.mark_failed(task.id, error="Handler declined task during triage")
                    tasks_processed += 1
                    continue

                await self._store.update_status(task.id, TaskStatus.EXECUTING)
                result = await handler.execute(task)

                await self._store.update_status(task.id, TaskStatus.VERIFYING)
                verified = await handler.verify(task)
                if not verified:
                    await self._store.mark_failed(task.id, error="Verification failed")
                    tasks_processed += 1
                    continue

                await self._store.update_status(task.id, TaskStatus.DELIVERING)
                delivery = await handler.deliver(task)

                final_result = {**result, **delivery}
                await self._store.mark_completed(task.id, final_result)
                tasks_processed += 1

            except Exception as e:
                logger.exception(f"Error processing task {task.id}")
                await self._store.mark_failed(task.id, error=str(e))
                tasks_processed += 1

        return tasks_processed

    async def run_loop(self, poll_interval: float = 300):
        """Run the coordinator loop indefinitely. Used by the FastAPI lifespan."""
        logger.info(f"Coordinator loop started (interval={poll_interval}s)")
        while True:
            try:
                processed = await self.tick()
                if processed > 0:
                    logger.info(f"Processed {processed} tasks")
            except Exception:
                logger.exception("Error in coordinator loop")
            await asyncio.sleep(poll_interval)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_coordinator.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add forge/coordinator.py tests/test_coordinator.py
git commit -m "feat: add coordinator with task dispatch loop"
```

---

### Task 9: FastAPI App with Lifespan and Task API

**Files:**
- Modify: `forge/main.py`
- Create: `forge/api/__init__.py`
- Create: `forge/api/tasks.py`
- Create: `forge/api/health.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_api.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient

from forge.db import Database
from forge.main import create_app


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def client(db):
    app = create_app(db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_create_task(client):
    resp = await client.post(
        "/api/tasks",
        json={
            "type": "echo",
            "title": "Test task",
            "description": "Created via API",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test task"
    assert data["status"] == "queued"
    assert data["source"] == "chat"
    assert "id" in data


async def test_get_task(client):
    create_resp = await client.post(
        "/api/tasks",
        json={
            "type": "code",
            "title": "Get me",
            "description": "Fetch test",
        },
    )
    task_id = create_resp.json()["id"]

    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Get me"


async def test_get_nonexistent_task(client):
    resp = await client.get("/api/tasks/nonexistent")
    assert resp.status_code == 404


async def test_list_tasks(client):
    for i in range(3):
        await client.post(
            "/api/tasks",
            json={
                "type": "code",
                "title": f"Task {i}",
                "description": f"List test {i}",
            },
        )

    resp = await client.get("/api/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3


async def test_list_tasks_filter_by_status(client):
    await client.post(
        "/api/tasks",
        json={"type": "code", "title": "Queued", "description": "Will stay queued"},
    )

    resp = await client.get("/api/tasks?status=queued")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await client.get("/api/tasks?status=completed")
    assert resp.status_code == 200
    assert len(resp.json()) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api.py -v`
Expected: FAIL with "ImportError" (create_app doesn't exist yet)

- [ ] **Step 3: Write forge/api/__init__.py**

```python
```

(Empty file — package marker.)

- [ ] **Step 4: Write forge/api/health.py**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Write forge/api/tasks.py**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from forge.models import Task, TaskSource, TaskStatus, TaskType
from forge.store import TaskStore

router = APIRouter(prefix="/api/tasks")

_store: TaskStore | None = None


def set_store(store: TaskStore):
    global _store
    _store = store


def get_store() -> TaskStore:
    assert _store is not None
    return _store


class CreateTaskRequest(BaseModel):
    type: str
    title: str
    description: str
    repo: str | None = None
    source_id: str | None = None


@router.post("", status_code=201)
async def create_task(req: CreateTaskRequest):
    store = get_store()
    task = Task.new(
        task_type=TaskType(req.type) if req.type in TaskType.__members__.values() else req.type,
        source=TaskSource.CHAT,
        title=req.title,
        description=req.description,
        repo=req.repo,
        source_id=req.source_id,
    )
    await store.save(task)
    return task.model_dump(mode="json")


@router.get("/{task_id}")
async def get_task(task_id: str):
    store = get_store()
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.model_dump(mode="json")


@router.get("")
async def list_tasks(status: str | None = None):
    store = get_store()
    if status:
        tasks = await store.list_by_status(TaskStatus(status))
    else:
        tasks = await store.list_by_status(TaskStatus.QUEUED)
        for s in [TaskStatus.TRIAGING, TaskStatus.EXECUTING, TaskStatus.VERIFYING,
                   TaskStatus.DELIVERING, TaskStatus.COMPLETED, TaskStatus.FAILED]:
            tasks.extend(await store.list_by_status(s))
    return [t.model_dump(mode="json") for t in tasks]
```

- [ ] **Step 6: Rewrite forge/main.py**

```python
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from forge.api import health, tasks
from forge.config import Settings
from forge.coordinator import Coordinator
from forge.db import Database
from forge.handlers import HandlerRegistry
from forge.handlers.echo import EchoHandler
from forge.store import TaskStore


def create_app(db: Database | None = None) -> FastAPI:
    app = FastAPI(title="Ardent Forge")
    app.include_router(health.router)
    app.include_router(tasks.router)

    if db is not None:
        store = TaskStore(db)
        tasks.set_store(store)

    return app


def run():
    settings = Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.db_path)
        await db.initialize()

        store = TaskStore(db)
        tasks.set_store(store)

        registry = HandlerRegistry()
        registry.register(EchoHandler())

        coordinator = Coordinator(
            store=store,
            registry=registry,
            max_concurrent=settings.max_concurrent_tasks,
        )

        loop_task = asyncio.create_task(
            coordinator.run_loop(poll_interval=settings.poll_interval_seconds)
        )

        yield

        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass
        await db.close()

    app = create_app()
    app.router.lifespan_context = lifespan
    uvicorn.run(app, host=settings.host, port=settings.port)
```

- [ ] **Step 7: Update tests/conftest.py**

```python
import pytest
from forge.db import Database


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.initialize()
    yield database
    await database.close()
```

- [ ] **Step 8: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass (across all test files)

- [ ] **Step 9: Verify the app starts**

Run: `FORGE_ANTHROPIC_API_KEY=test FORGE_GITHUB_TOKEN=test uv run forge`
Expected: Uvicorn starts, coordinator loop logs "Coordinator loop started"

Ctrl-C to stop.

- [ ] **Step 10: Commit**

```bash
git add forge/main.py forge/api/ tests/test_api.py tests/conftest.py
git commit -m "feat: add FastAPI app with task API and coordinator lifespan"
```

---

### Task 10: Graceful Shutdown and Resume

**Files:**
- Modify: `forge/coordinator.py`
- Modify: `forge/store.py`
- Create: `tests/test_resume.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_resume.py`:
```python
import pytest

from forge.db import Database
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


async def test_reset_in_progress_tasks(store):
    """On startup, any task stuck in a non-terminal active state should be reset to queued."""
    task_executing = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Was executing",
        description="Stuck",
    )
    await store.save(task_executing)
    await store.update_status(task_executing.id, TaskStatus.EXECUTING)

    task_verifying = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Was verifying",
        description="Also stuck",
    )
    await store.save(task_verifying)
    await store.update_status(task_verifying.id, TaskStatus.VERIFYING)

    task_completed = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Already done",
        description="Should not change",
    )
    await store.save(task_completed)
    await store.mark_completed(task_completed.id, {"done": True})

    reset_count = await store.reset_active_tasks()
    assert reset_count == 2

    t1 = await store.get(task_executing.id)
    assert t1 is not None
    assert t1.status == TaskStatus.QUEUED

    t2 = await store.get(task_verifying.id)
    assert t2 is not None
    assert t2.status == TaskStatus.QUEUED

    t3 = await store.get(task_completed.id)
    assert t3 is not None
    assert t3.status == TaskStatus.COMPLETED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_resume.py -v`
Expected: FAIL with "AttributeError: 'TaskStore' object has no attribute 'reset_active_tasks'"

- [ ] **Step 3: Add reset_active_tasks to store.py**

Add this method to the `TaskStore` class in `forge/store.py`:

```python
    async def reset_active_tasks(self) -> int:
        """Reset any tasks stuck in active (non-terminal) states back to queued.
        Called on startup to recover from unclean shutdown."""
        now = datetime.now(timezone.utc).isoformat()
        active_states = (
            TaskStatus.TRIAGING.value,
            TaskStatus.EXECUTING.value,
            TaskStatus.VERIFYING.value,
            TaskStatus.DELIVERING.value,
        )
        placeholders = ", ".join("?" for _ in active_states)
        cursor = await self._db.execute(
            f"UPDATE tasks SET status = ?, updated_at = ? WHERE status IN ({placeholders})",
            (TaskStatus.QUEUED.value, now, *active_states),
        )
        return cursor.rowcount
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_resume.py -v`
Expected: 1 passed

- [ ] **Step 5: Add reset call to coordinator startup**

Add this method to the `Coordinator` class in `forge/coordinator.py`:

```python
    async def startup(self):
        """Called once on application start. Resets stuck tasks."""
        reset_count = await self._store.reset_active_tasks()
        if reset_count > 0:
            logger.info(f"Reset {reset_count} stuck tasks to queued on startup")
```

- [ ] **Step 6: Call startup from main.py lifespan**

In `forge/main.py`, inside the `lifespan` function, add after creating the coordinator:

```python
        await coordinator.startup()
```

(Add this line right before `loop_task = asyncio.create_task(...)`)

- [ ] **Step 7: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add forge/store.py forge/coordinator.py forge/main.py tests/test_resume.py
git commit -m "feat: add graceful shutdown recovery — reset stuck tasks on startup"
```

---

### Task 11: Run Full Test Suite and Verify

**Files:** None (verification only)

- [ ] **Step 1: Run the complete test suite**

```bash
uv run pytest -v --tb=short
```

Expected: All tests pass across all files.

- [ ] **Step 2: Verify the app starts and accepts requests**

```bash
FORGE_ANTHROPIC_API_KEY=test FORGE_GITHUB_TOKEN=test uv run forge &
sleep 2
curl -s http://localhost:7030/health | python -m json.tool
curl -s -X POST http://localhost:7030/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"type": "echo", "title": "Hello Forge", "description": "First task"}' | python -m json.tool
curl -s http://localhost:7030/api/tasks | python -m json.tool
kill %1
```

Expected:
- Health returns `{"status": "ok"}`
- Task creation returns 201 with task data
- Task list returns the created task
- After coordinator tick, the echo task should be completed

- [ ] **Step 3: Create .gitignore**

```gitignore
__pycache__/
*.pyc
.venv/
forge.db
*.egg-info/
dist/
.pytest_cache/
```

- [ ] **Step 4: Final commit**

```bash
git add .gitignore
git commit -m "chore: add .gitignore"
```
