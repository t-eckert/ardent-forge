# Forge MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose Forge's task pipeline, memory, repos, schedules, notebook, and web search to Claude Code sessions on the box via an MCP server mounted in-process at `/mcp`.

**Architecture:** A `forge/mcp/` module builds a FastMCP (official `mcp` SDK) server whose tools are thin wrappers over Forge's already-assembled services. Services are injected via a module-level `configure(...)` (same pattern as `forge/api/chat.py`). The FastMCP streamable-HTTP app is mounted into the existing FastAPI app, and its session manager is run from Forge's lifespan.

**Tech Stack:** Python 3.13, FastAPI/Starlette, `mcp` Python SDK (FastMCP, streamable HTTP), pytest + pytest-asyncio (`asyncio_mode = "auto"`).

---

## Reference: confirmed APIs

These signatures are verified against the codebase — use them exactly:

- `Task.new(task_type: TaskType | str, source: TaskSource, title: str, description: str, repo: str | None = None, source_id: str | None = None) -> Task`
- `TaskType`, `TaskSource`, `TaskStatus` are `StrEnum`s in `forge/models.py`. Chat coerces type with: `TaskType(t) if t in TaskType.__members__.values() else t`.
- `TaskStore`: `await save(task)`, `await get(id) -> Task | None`, `await list_all(limit=100) -> list[Task]`, `await list_by_status(TaskStatus) -> list[Task]`, `await save_schedule(name, cron_expr, task_type, task_template=None) -> str`, `await list_schedules() -> list[dict]`, `await get_schedule(id) -> dict | None`, `await delete_schedule(id)`.
- `task.model_dump(mode="json")` → JSON-safe dict (includes `status`, `result`, and `handler_data` which carries `zellij_session`/`attach_cmd` for Code tasks).
- `MemoryStore(root)` (sync): `.list() -> list[MemoryEntry]`, `.get(filename) -> MemoryEntry | None`, `.write(name, description, type, body, filename=None) -> MemoryEntry`, `.remove(filename) -> bool`. `MemoryEntry` has `.filename, .slug, .name, .description, .type, .body, .updated_at`. `VALID_TYPES = ("user","feedback","project","reference")` from `forge.memory`.
- `RepoRegistry`: `.list() -> list[Repo]`, `.get(name) -> Repo | None`. `Repo` is a Pydantic model → `.model_dump(mode="json")`.
- `NotebookReader`: `.search(query, path_prefix=None) -> list[SearchHit]` (SearchHit has `.path, .line_number, .line`), `.read(path) -> str` (raises `FileNotFoundError`/`ValueError`).
- `ConnectorRegistry.find_tool(name) -> Tool | None`; `Tool.execute` is an async callable taking kwargs, returning a dict.
- `Coordinator.nudge()` is a **sync** method.
- `create_app(db=None)` in `forge/main.py` builds the FastAPI app and wires the store. Tests use `httpx.AsyncClient(transport=ASGITransport(app=app))`.
- conftest provides only `db` and `agent_ctx` fixtures. Tests build `TaskStore(db)` / `MemoryStore(tmp_path)` themselves.

## File structure

- **Create** `forge/mcp/__init__.py` — exports `build_mcp_server`, `configure`.
- **Create** `forge/mcp/server.py` — module-level service refs, `configure(...)`, the async tool functions, `build_mcp_server(settings)`.
- **Modify** `forge/main.py` — build + mount the MCP server in `create_app`; inject services and run the session manager in the lifespan.
- **Modify** `pyproject.toml` — add `mcp` dependency.
- **Create** `tests/test_mcp.py` — unit tests per tool, conditional-registration tests, transport round-trip test.
- **Modify** `CLAUDE.md` — document the MCP server and client setup.

---

## Task 1: Add dependency and module skeleton

**Files:**
- Modify: `pyproject.toml`
- Create: `forge/mcp/__init__.py`
- Create: `forge/mcp/server.py`

- [ ] **Step 1: Add the `mcp` dependency**

In `pyproject.toml`, add to the `dependencies` list:

```toml
    "mcp>=1.2",
```

Then run `uv sync` and verify the import + symbols exist:

```bash
uv sync
uv run python -c "from mcp.server.fastmcp import FastMCP; s=FastMCP(name='probe', stateless_http=True); app=s.streamable_http_app(); print(type(app).__name__, hasattr(s,'session_manager'), hasattr(s,'add_tool'))"
```

Expected: prints something like `Starlette True True`. If `session_manager` or `streamable_http_app` differ in the installed version, note the actual names — every later task that references them must match. Also confirm the in-memory test helper exists:

```bash
uv run python -c "from mcp.shared.memory import create_connected_server_and_client_session as f; print('ok')"
```

Expected: `ok`. If this import path differs, record the correct one for Task 9.

- [ ] **Step 2: Write the skeleton `forge/mcp/server.py`**

```python
"""Forge MCP server — exposes Forge's services to local Claude Code sessions.

A FastMCP streamable-HTTP server mounted into the Forge FastAPI app at /mcp.
Tools are thin wrappers over already-assembled services, injected via
``configure(...)`` (same pattern as forge/api/chat.py) so this module stays
import-light and avoids an import cycle with the coordinator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from forge.memory import VALID_TYPES, MemoryStore
from forge.models import Task, TaskSource, TaskStatus, TaskType

# Injected services — set by configure() during app lifespan. Typed loosely
# (coordinator/connectors/repo_registry/notebook_reader) to avoid import cycles.
_store = None
_memory: MemoryStore | None = None
_repo_registry = None
_coordinator = None  # has .nudge()
_connectors = None
_notebook_reader = None


def configure(
    *,
    store=None,
    memory=None,
    repo_registry=None,
    coordinator=None,
    connectors=None,
    notebook_reader=None,
) -> None:
    """Inject live services. Idempotent merge — only overwrites what's passed."""
    global _store, _memory, _repo_registry, _coordinator, _connectors, _notebook_reader
    if store is not None:
        _store = store
    if memory is not None:
        _memory = memory
    if repo_registry is not None:
        _repo_registry = repo_registry
    if coordinator is not None:
        _coordinator = coordinator
    if connectors is not None:
        _connectors = connectors
    if notebook_reader is not None:
        _notebook_reader = notebook_reader


def build_mcp_server(settings) -> FastMCP:
    """Construct the FastMCP server, registering tools available for this
    deployment. Conditional tools (notebook, web search) are registered only
    when their backing service is configured."""
    server = FastMCP(name="forge", stateless_http=True)
    return server


__all__ = ["build_mcp_server", "configure"]
```

- [ ] **Step 3: Write `forge/mcp/__init__.py`**

```python
from forge.mcp.server import build_mcp_server, configure

__all__ = ["build_mcp_server", "configure"]
```

- [ ] **Step 4: Verify it imports**

Run: `uv run python -c "from forge.mcp import build_mcp_server, configure; from forge.config import Settings; print(build_mcp_server(Settings()).name)"`
Expected: prints `forge`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock forge/mcp/__init__.py forge/mcp/server.py
git commit -m "feat(mcp): add mcp dependency and server skeleton"
```

---

## Task 2: Task tools (dispatch_task, get_task, list_tasks)

**Files:**
- Modify: `forge/mcp/server.py`
- Test: `tests/test_mcp.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_mcp.py`:

```python
import pytest

from forge.db import Database
from forge.mcp import server as mcp_server
from forge.models import TaskStatus
from forge.store import TaskStore


class _NudgeSpy:
    def __init__(self):
        self.calls = 0

    def nudge(self):
        self.calls += 1


@pytest.fixture
async def store():
    db = Database(":memory:")
    await db.initialize()
    yield TaskStore(db)
    await db.close()


@pytest.fixture(autouse=True)
def _reset_mcp_globals():
    # Each test configures its own services; clear between tests.
    mcp_server._store = None
    mcp_server._memory = None
    mcp_server._repo_registry = None
    mcp_server._coordinator = None
    mcp_server._connectors = None
    mcp_server._notebook_reader = None
    yield


async def test_dispatch_task_saves_and_nudges(store):
    spy = _NudgeSpy()
    mcp_server.configure(store=store, coordinator=spy)

    out = await mcp_server.dispatch_task(
        type="echo", title="Hello", description="Do the thing"
    )

    assert "id" in out
    assert out["status"] == TaskStatus.QUEUED.value
    assert spy.calls == 1
    saved = await store.get(out["id"])
    assert saved is not None
    assert saved.title == "Hello"


async def test_dispatch_task_rejects_oversize_title(store):
    mcp_server.configure(store=store)
    out = await mcp_server.dispatch_task(
        type="echo", title="x" * 501, description="d"
    )
    assert "error" in out


async def test_get_task_round_trip(store):
    mcp_server.configure(store=store)
    created = await mcp_server.dispatch_task(
        type="echo", title="T", description="D"
    )
    got = await mcp_server.get_task(created["id"])
    assert got["id"] == created["id"]
    assert got["title"] == "T"


async def test_get_task_not_found(store):
    mcp_server.configure(store=store)
    assert await mcp_server.get_task("nope") == {"error": "Task not found"}


async def test_list_tasks_filters_by_status(store):
    mcp_server.configure(store=store)
    await mcp_server.dispatch_task(type="echo", title="A", description="D")
    all_tasks = await mcp_server.list_tasks()
    assert len(all_tasks) == 1
    queued = await mcp_server.list_tasks(status="queued")
    assert len(queued) == 1
    done = await mcp_server.list_tasks(status="completed")
    assert done == []


async def test_list_tasks_invalid_status(store):
    mcp_server.configure(store=store)
    out = await mcp_server.list_tasks(status="bogus")
    assert isinstance(out, dict) and "error" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mcp.py -v`
Expected: FAIL — `AttributeError: module 'forge.mcp.server' has no attribute 'dispatch_task'`.

- [ ] **Step 3: Implement the task tools**

In `forge/mcp/server.py`, add these functions above `build_mcp_server`:

```python
async def dispatch_task(
    type: str, title: str, description: str, repo: str | None = None
) -> dict:
    """Queue a task for Forge's agent pipeline and start it processing now.

    Hands work off to a Forge agent (e.g. the Code agent runs Claude Code in a
    Zellij session). Returns immediately with the task id and status — this does
    NOT wait for completion. Poll get_task(id) or list_tasks() to observe progress
    and pick up the result (Code tasks expose zellij_session/attach_cmd in
    handler_data so you can attach to the live session).
    """
    if len(title) > 500:
        return {"error": "title exceeds 500 characters"}
    if len(description) > 50_000:
        return {"error": "description exceeds 50000 characters"}
    if len(type) > 64:
        return {"error": "type exceeds 64 characters"}

    task_type = type if type not in TaskType.__members__.values() else TaskType(type)
    task = Task.new(
        task_type=task_type,
        source=TaskSource.CHAT,
        title=title,
        description=description,
        repo=repo,
    )
    await _store.save(task)
    if _coordinator is not None and hasattr(_coordinator, "nudge"):
        _coordinator.nudge()
    return {"id": task.id, "status": task.status.value}


async def get_task(task_id: str) -> dict:
    """Fetch a task's full state (status, result, handler_data) by id."""
    task = await _store.get(task_id)
    if task is None:
        return {"error": "Task not found"}
    return task.model_dump(mode="json")


async def list_tasks(status: str | None = None, type: str | None = None) -> Any:
    """List recent tasks, optionally filtered by status and/or type. Use for
    polling dispatched work."""
    if status:
        try:
            target = TaskStatus(status)
        except ValueError:
            return {"error": f"invalid status: {status}"}
        tasks = await _store.list_by_status(target)
    else:
        tasks = await _store.list_all()
    if type:
        tasks = [t for t in tasks if str(t.type) == type]
    return [t.model_dump(mode="json") for t in tasks]
```

- [ ] **Step 4: Register them in `build_mcp_server`**

Replace the body of `build_mcp_server` (between creating `server` and `return server`) with:

```python
    server.add_tool(dispatch_task, name="dispatch_task")
    server.add_tool(get_task, name="get_task")
    server.add_tool(list_tasks, name="list_tasks")
```

(FastMCP derives each tool's description and parameter schema from the function's docstring and type hints.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_mcp.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add forge/mcp/server.py tests/test_mcp.py
git commit -m "feat(mcp): task dispatch and observation tools"
```

---

## Task 3: Memory tools

**Files:**
- Modify: `forge/mcp/server.py`
- Test: `tests/test_mcp.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_mcp.py`:

```python
from forge.memory import MemoryStore


@pytest.fixture
def memory(tmp_path):
    return MemoryStore(tmp_path)


async def test_memory_write_read_list_delete(memory):
    mcp_server.configure(memory=memory)

    written = await mcp_server.write_memory(
        name="Likes tabs",
        description="prefers tabs",
        type="user",
        body="The user prefers tabs over spaces.",
    )
    assert written["name"] == "Likes tabs"
    fname = written["filename"]

    listed = await mcp_server.list_memory()
    assert any(e["filename"] == fname for e in listed)

    read = await mcp_server.read_memory(fname)
    assert read["body"] == "The user prefers tabs over spaces."

    deleted = await mcp_server.delete_memory(fname)
    assert deleted == {"deleted": fname}
    assert (await mcp_server.read_memory(fname)) == {
        "error": f"No memory: {fname}"
    }


async def test_memory_write_rejects_bad_type(memory):
    mcp_server.configure(memory=memory)
    out = await mcp_server.write_memory(
        name="x", description="y", type="bogus", body="z"
    )
    assert "error" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mcp.py -k memory -v`
Expected: FAIL — `write_memory` not defined.

- [ ] **Step 3: Implement the memory tools**

In `forge/mcp/server.py`, add above `build_mcp_server`:

```python
def _mem_dict(entry) -> dict:
    return {
        "filename": entry.filename,
        "slug": entry.slug,
        "name": entry.name,
        "description": entry.description,
        "type": entry.type,
        "body": entry.body,
        "updated_at": entry.updated_at,
    }


async def list_memory() -> list[dict]:
    """List Forge's memory entries (shared with chat/Linear sessions)."""
    return [_mem_dict(e) for e in _memory.list()]


async def read_memory(filename: str) -> dict:
    """Read one memory entry, including its full body."""
    entry = _memory.get(filename)
    if entry is None:
        return {"error": f"No memory: {filename}"}
    return _mem_dict(entry)


async def write_memory(
    name: str, description: str, type: str, body: str, filename: str | None = None
) -> dict:
    """Create or update a memory entry. type is one of: user, feedback,
    project, reference. Writes regenerate MEMORY.md automatically."""
    if type not in VALID_TYPES:
        return {"error": f"invalid type: {type}; must be one of {', '.join(VALID_TYPES)}"}
    entry = _memory.write(
        name=name, description=description, type=type, body=body, filename=filename
    )
    return _mem_dict(entry)


async def delete_memory(filename: str) -> dict:
    """Delete a memory entry by filename."""
    if _memory.remove(filename):
        return {"deleted": filename}
    return {"error": f"No memory: {filename}"}
```

- [ ] **Step 4: Register them in `build_mcp_server`**

Add after the task tool registrations:

```python
    server.add_tool(list_memory, name="list_memory")
    server.add_tool(read_memory, name="read_memory")
    server.add_tool(write_memory, name="write_memory")
    server.add_tool(delete_memory, name="delete_memory")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_mcp.py -k memory -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add forge/mcp/server.py tests/test_mcp.py
git commit -m "feat(mcp): memory read/write tools"
```

---

## Task 4: Repo tools

**Files:**
- Modify: `forge/mcp/server.py`
- Test: `tests/test_mcp.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_mcp.py`:

```python
from forge.repos.models import Repo


class _FakeRegistry:
    def __init__(self, repos):
        self._repos = repos

    def list(self):
        return self._repos

    def get(self, name):
        return next((r for r in self._repos if r.name == name), None)


def _repo(name):
    return Repo(name=name, path=f"/repos/{name}", default_branch="main")


async def test_list_and_get_repos():
    reg = _FakeRegistry([_repo("alpha"), _repo("beta")])
    mcp_server.configure(repo_registry=reg)

    repos = await mcp_server.list_repos()
    assert {r["name"] for r in repos} == {"alpha", "beta"}

    one = await mcp_server.get_repo("alpha")
    assert one["name"] == "alpha"

    missing = await mcp_server.get_repo("zeta")
    assert missing == {"error": "Repo not found: zeta"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mcp.py -k repo -v`
Expected: FAIL — `list_repos` not defined.

- [ ] **Step 3: Implement the repo tools**

In `forge/mcp/server.py`, add above `build_mcp_server`:

```python
async def list_repos() -> list[dict]:
    """List workspace repos (name, path, dev_port, env, claude_label)."""
    return [r.model_dump(mode="json") for r in _repo_registry.list()]


async def get_repo(name: str) -> dict:
    """Fetch a single workspace repo's config by name."""
    repo = _repo_registry.get(name)
    if repo is None:
        return {"error": f"Repo not found: {name}"}
    return repo.model_dump(mode="json")
```

- [ ] **Step 4: Register them in `build_mcp_server`**

```python
    server.add_tool(list_repos, name="list_repos")
    server.add_tool(get_repo, name="get_repo")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_mcp.py -k repo -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add forge/mcp/server.py tests/test_mcp.py
git commit -m "feat(mcp): repo listing tools"
```

---

## Task 5: Schedule tools

**Files:**
- Modify: `forge/mcp/server.py`
- Test: `tests/test_mcp.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_mcp.py`:

```python
async def test_schedule_create_list_delete(store):
    mcp_server.configure(store=store)

    created = await mcp_server.create_schedule(
        name="Nightly",
        cron_expr="0 2 * * *",
        task_type="code",
        repo="t-eckert/ardent-forge",
        prompt_template="Run the nightly maintenance pass",
        label="maint",
    )
    sid = created["id"]
    assert created["name"] == "Nightly"

    listed = await mcp_server.list_schedules()
    assert any(s["id"] == sid for s in listed)

    deleted = await mcp_server.delete_schedule(sid)
    assert deleted == {"deleted": sid}

    assert await mcp_server.delete_schedule(sid) == {"error": "Schedule not found"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mcp.py -k schedule -v`
Expected: FAIL — `create_schedule` not defined.

- [ ] **Step 3: Implement the schedule tools**

In `forge/mcp/server.py`, add above `build_mcp_server`:

```python
async def list_schedules() -> list[dict]:
    """List cron schedules that fire Forge tasks."""
    return await _store.list_schedules()


async def create_schedule(
    name: str,
    cron_expr: str,
    task_type: str,
    repo: str | None = None,
    prompt_template: str | None = None,
    label: str | None = None,
) -> dict:
    """Create a cron schedule. cron_expr is standard 5-field cron. For Code
    tasks, repo is GitHub owner/name and prompt_template becomes the task
    description on each fire."""
    template: dict = {}
    if repo:
        template["repo"] = repo
    if prompt_template:
        template["description"] = prompt_template
    if label:
        template["label"] = label
    if prompt_template and not template.get("title"):
        template["title"] = prompt_template.splitlines()[0][:120]
    schedule_id = await _store.save_schedule(
        name=name, cron_expr=cron_expr, task_type=task_type, task_template=template
    )
    return await _store.get_schedule(schedule_id)


async def delete_schedule(schedule_id: str) -> dict:
    """Delete a cron schedule by id."""
    if await _store.get_schedule(schedule_id) is None:
        return {"error": "Schedule not found"}
    await _store.delete_schedule(schedule_id)
    return {"deleted": schedule_id}
```

- [ ] **Step 4: Register them in `build_mcp_server`**

```python
    server.add_tool(list_schedules, name="list_schedules")
    server.add_tool(create_schedule, name="create_schedule")
    server.add_tool(delete_schedule, name="delete_schedule")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_mcp.py -k schedule -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add forge/mcp/server.py tests/test_mcp.py
git commit -m "feat(mcp): cron schedule tools"
```

---

## Task 6: Conditional notebook + web search tools

**Files:**
- Modify: `forge/mcp/server.py`
- Test: `tests/test_mcp.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_mcp.py`:

```python
class _FakeHit:
    def __init__(self, path, line_number, line):
        self.path = path
        self.line_number = line_number
        self.line = line


class _FakeReader:
    def search(self, query, path_prefix=None):
        return [_FakeHit("notes/a.md", 3, f"match for {query}")]

    def read(self, path):
        if path == "notes/a.md":
            return "file body"
        raise FileNotFoundError(path)


async def test_search_notebook_and_read_note():
    mcp_server.configure(notebook_reader=_FakeReader())

    hits = await mcp_server.search_notebook("foo")
    assert hits == [{"path": "notes/a.md", "line_number": 3, "line": "match for foo"}]

    note = await mcp_server.read_note("notes/a.md")
    assert note == {"path": "notes/a.md", "content": "file body"}

    missing = await mcp_server.read_note("notes/missing.md")
    assert "error" in missing


class _FakeTool:
    async def execute(self, **kwargs):
        return {"query": kwargs.get("query"), "results": []}


class _FakeConnectors:
    def __init__(self, tool):
        self._tool = tool

    def find_tool(self, name):
        return self._tool if name == "web_search" else None


async def test_web_search_uses_connector_tool():
    mcp_server.configure(connectors=_FakeConnectors(_FakeTool()))
    out = await mcp_server.web_search("latest python release")
    assert out["query"] == "latest python release"


async def test_web_search_missing_connector():
    mcp_server.configure(connectors=_FakeConnectors(None))
    out = await mcp_server.web_search("anything")
    assert out == {"error": "web search not configured"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mcp.py -k "notebook or web_search or read_note" -v`
Expected: FAIL — `search_notebook` not defined.

- [ ] **Step 3: Implement the conditional tools**

In `forge/mcp/server.py`, add above `build_mcp_server`:

```python
async def search_notebook(query: str) -> list[dict]:
    """Full-text search the read-only Obsidian notebook. Returns matching
    file paths, line numbers, and lines."""
    return [
        {"path": h.path, "line_number": h.line_number, "line": h.line}
        for h in _notebook_reader.search(query)
    ]


async def read_note(path: str) -> dict:
    """Read a note from the read-only notebook by vault-relative path."""
    try:
        return {"path": path, "content": _notebook_reader.read(path)}
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}


async def web_search(query: str, max_results: int = 5) -> dict:
    """Search the web for current information via Forge's web-search connector."""
    tool = _connectors.find_tool("web_search") if _connectors is not None else None
    if tool is None:
        return {"error": "web search not configured"}
    return await tool.execute(query=query, max_results=max_results)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_mcp.py -k "notebook or web_search or read_note" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/mcp/server.py tests/test_mcp.py
git commit -m "feat(mcp): conditional notebook and web search tools"
```

---

## Task 7: Conditional registration in build_mcp_server

**Files:**
- Modify: `forge/mcp/server.py`
- Test: `tests/test_mcp.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_mcp.py`:

```python
from forge.config import Settings
from forge.mcp import build_mcp_server

ALWAYS_ON = {
    "dispatch_task",
    "get_task",
    "list_tasks",
    "list_memory",
    "read_memory",
    "write_memory",
    "delete_memory",
    "list_repos",
    "get_repo",
    "list_schedules",
    "create_schedule",
    "delete_schedule",
}


async def _tool_names(server):
    return {t.name for t in await server.list_tools()}


async def test_always_on_tools_registered(tmp_path):
    settings = Settings(notebook_dir=str(tmp_path / "missing"), tavily_api_key="")
    names = await _tool_names(build_mcp_server(settings))
    assert ALWAYS_ON <= names
    assert "search_notebook" not in names
    assert "read_note" not in names
    assert "web_search" not in names


async def test_notebook_tools_registered_when_dir_exists(tmp_path):
    nb = tmp_path / "vault"
    nb.mkdir()
    settings = Settings(notebook_dir=str(nb), tavily_api_key="")
    names = await _tool_names(build_mcp_server(settings))
    assert {"search_notebook", "read_note"} <= names


async def test_web_search_registered_when_tavily_set(tmp_path):
    settings = Settings(notebook_dir=str(tmp_path / "missing"), tavily_api_key="tvly-x")
    names = await _tool_names(build_mcp_server(settings))
    assert "web_search" in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mcp.py -k "registered" -v`
Expected: FAIL — conditional tools not registered (notebook/web_search absent even when configured).

- [ ] **Step 3: Add conditional registration**

In `forge/mcp/server.py`, add to `build_mcp_server` after the always-on registrations and before `return server`:

```python
    if Path(settings.notebook_dir).is_dir():
        server.add_tool(search_notebook, name="search_notebook")
        server.add_tool(read_note, name="read_note")

    if settings.tavily_api_key:
        server.add_tool(web_search, name="web_search")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_mcp.py -k "registered" -v`
Expected: PASS.

- [ ] **Step 5: Run the whole MCP test file**

Run: `uv run pytest tests/test_mcp.py -v`
Expected: PASS (all tasks so far).

- [ ] **Step 6: Commit**

```bash
git add forge/mcp/server.py tests/test_mcp.py
git commit -m "feat(mcp): conditional tool registration by settings"
```

---

## Task 8: Mount the MCP server and run its session manager

**Files:**
- Modify: `forge/main.py`

- [ ] **Step 1: Build + mount the server in `create_app`**

In `forge/main.py`, change the `create_app` signature and add the mount. Replace:

```python
def create_app(db: Database | None = None) -> FastAPI:
    app = FastAPI(title="Ardent Forge")
    app.include_router(health.router)
```

with:

```python
def create_app(db: Database | None = None, settings: "Settings | None" = None) -> FastAPI:
    app = FastAPI(title="Ardent Forge")

    # MCP server — mounted in-process so its tools call Forge's services
    # directly. Services are injected via mcp.configure() in the lifespan;
    # the session manager is run there too. Conditional tools are decided
    # from settings here at build time.
    from forge.mcp import build_mcp_server

    mcp_server = build_mcp_server(settings or Settings())
    app.state.mcp_server = mcp_server
    app.mount("/mcp", mcp_server.streamable_http_app())

    app.include_router(health.router)
```

`Settings` is already imported at the top of `main.py` (`from forge.config import Settings`).

- [ ] **Step 2: Inject services in the lifespan**

In `run()`'s `lifespan`, after the orchestrator/coordinator are assembled and `app.state.coordinator = coordinator` is set (near the end, before `await coordinator.startup()`), add:

```python
        # Wire the MCP server's tools to the live services.
        from forge.mcp import configure as mcp_configure

        mcp_configure(
            store=store,
            memory=memory_store,
            repo_registry=repo_registry,
            coordinator=coordinator,
            connectors=connectors,
            notebook_reader=notebook_reader,
        )
```

- [ ] **Step 3: Run the MCP session manager around the lifespan yield**

In the same `lifespan`, wrap the existing `yield` so the FastMCP streamable-HTTP session manager runs for the app's lifetime. Replace:

```python
        loop_task = asyncio.create_task(
            coordinator.run_loop(poll_interval=settings.poll_interval_seconds)
        )

        yield

        loop_task.cancel()
```

with:

```python
        loop_task = asyncio.create_task(
            coordinator.run_loop(poll_interval=settings.poll_interval_seconds)
        )

        async with app.state.mcp_server.session_manager.run():
            yield

        loop_task.cancel()
```

> If Step 1 of Task 1 found that `session_manager` / `streamable_http_app` have different names in the installed `mcp` version, use those names here instead.

- [ ] **Step 4: Pass settings into create_app from run()**

In `run()`, the line `app = create_app()` is near the bottom. Change it to reuse the already-constructed settings:

```python
    app = create_app(settings=settings)
```

- [ ] **Step 5: Verify the app boots and the route exists**

Run: `uv run python -c "from forge.main import create_app; app=create_app(); print(any(getattr(r,'path','')=='/mcp' for r in app.routes))"`
Expected: prints `True`.

Then verify the full suite still imports/builds the app:

Run: `uv run pytest tests/test_api.py -q`
Expected: PASS (no regressions from the `create_app` signature change).

- [ ] **Step 6: Commit**

```bash
git add forge/main.py
git commit -m "feat(mcp): mount MCP server and run session manager in lifespan"
```

---

## Task 9: Transport round-trip integration test

**Files:**
- Test: `tests/test_mcp.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mcp.py`:

```python
from mcp.shared.memory import create_connected_server_and_client_session


async def test_transport_round_trip(store, tmp_path):
    # Build a server with the always-on tools and wire live services.
    settings = Settings(notebook_dir=str(tmp_path / "missing"), tavily_api_key="")
    server = build_mcp_server(settings)
    mcp_server.configure(store=store)

    # create_connected_server_and_client_session connects an in-memory client
    # to the low-level server, exercising the real MCP protocol (no HTTP).
    async with create_connected_server_and_client_session(
        server._mcp_server
    ) as client:
        listed = await client.list_tools()
        names = {t.name for t in listed.tools}
        assert ALWAYS_ON <= names

        result = await client.call_tool(
            "dispatch_task",
            {"type": "echo", "title": "Round trip", "description": "via MCP"},
        )
        assert result.isError is False

    # The dispatched task really landed in the store.
    tasks = await store.list_all()
    assert any(t.title == "Round trip" for t in tasks)
```

> If Task 1 Step 1 recorded a different import path or the low-level server is exposed under a different attribute than `server._mcp_server`, adjust this test accordingly. `call_tool` return shape (`.isError`, `.content`) is from the `mcp` SDK client; if the installed version differs, assert on the store side-effect (`tasks` check) as the primary signal.

- [ ] **Step 2: Run the test to verify it fails, then passes**

Run: `uv run pytest tests/test_mcp.py::test_transport_round_trip -v`
Expected: initially this should PASS if the wiring is correct (the implementation already exists). If it FAILS due to SDK API mismatch, fix the test per the note above until it passes. The meaningful assertions are: `tools/list` includes the always-on set, and the `dispatch_task` call creates a task in the store.

- [ ] **Step 3: Run the full MCP suite**

Run: `uv run pytest tests/test_mcp.py -v`
Expected: PASS (all tests).

- [ ] **Step 4: Commit**

```bash
git add tests/test_mcp.py
git commit -m "test(mcp): transport round-trip via in-memory client session"
```

---

## Task 10: Documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Document the MCP server in CLAUDE.md**

In `CLAUDE.md`, under the `### Backend: forge/` section's "Key modules" list, add a bullet:

```markdown
- `forge/mcp/` — FastMCP server mounted at `/mcp`; exposes Forge's tasks, memory, repos, schedules, and (when configured) notebook + web search to local Claude Code sessions. Tools wrap existing services, injected via `configure()` in `main.py`'s lifespan.
```

- [ ] **Step 2: Add a client-setup note**

In `CLAUDE.md`, under `## Commands`, after the backend block, add:

````markdown
```bash
# MCP server (exposed by the running backend at /mcp)
claude mcp add --transport http forge http://localhost:7030/mcp                       # on the box
claude mcp add --transport http forge https://ardent-forge.feist-gondola.ts.net/mcp   # from another tailnet device (via Caddy)
```
````

- [ ] **Step 3: Run the full backend test suite**

Run: `uv run pytest -q`
Expected: PASS (no regressions).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(mcp): document Forge MCP server and client setup"
```

---

## Post-implementation manual verification (deployment)

Not a unit test — run after deploying with `sudo systemctl restart ardent-forge`:

1. On the box: `claude mcp add --transport http forge http://localhost:7030/mcp`, then in a session confirm the `forge` tools appear and `dispatch_task` → `get_task` works.
2. From the Mac over Tailscale via the Caddy host (`https://ardent-forge.feist-gondola.ts.net/mcp`), confirm the same. This validates that Caddy's `reverse_proxy` streams the long-lived MCP responses without buffering (expected to work — Caddy flushes by default; this is the explicit check called out in the spec).

---

## Self-review notes

- **Spec coverage:** task tools (Task 2), memory (3), repos (4), schedules (5), conditional notebook/web search (6, 7), HTTP mount + lifespan composition + dependency (1, 8), error-as-dict handling (throughout), conditional registration (7), unit + conditional + transport tests (2–9), client-setup URLs incl. Caddy/streaming check (10 + manual). All spec sections map to a task.
- **No placeholders:** every code step contains complete code; commands have expected output.
- **Type/name consistency:** `build_mcp_server`/`configure` names match across module, `main.py`, and tests; tool function names match their `add_tool(name=...)` registrations and the `ALWAYS_ON` set; `_store/_memory/_repo_registry/_coordinator/_connectors/_notebook_reader` globals are consistent between `configure`, the tools, and the test reset fixture.
- **Version risk flagged:** Task 1 Step 1 verifies the exact `mcp` SDK symbols (`streamable_http_app`, `session_manager`, `create_connected_server_and_client_session`, `server._mcp_server`); Tasks 8 and 9 reference those and note the fallback if names differ.
