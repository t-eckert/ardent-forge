# Task Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the task pipeline resilient — auto-retry transient failures and timeouts with backoff, bound execution time and reclaim slots from hung work, and allow a human to requeue a failed task on demand.

**Architecture:** A pure `forge/retry.py` module holds the backoff math and failure-kind classification. The `Task` model + SQLite schema gain `max_retries`, `available_at` (backoff gate), and `failure_kind`. `TaskStore` learns to record failure kinds, gate `list_pending` on `available_at`, requeue with backoff, list active tasks, and clear a task for manual retry. The `Coordinator` routes every failure path through one `_fail_or_retry` helper that tears down any orphaned Zellij session, then retries-with-backoff or fails terminally; it wraps producing stages in `asyncio.wait_for` (in-process timeout) and runs a reaper on startup and each tick (restart backstop). A new `POST /api/tasks/{id}/retry` endpoint exposes manual requeue.

**Tech Stack:** Python 3.13, FastAPI, aiosqlite, pytest + pytest-asyncio (`asyncio_mode = "auto"`), Pydantic v2.

---

## File Structure

- **Create `forge/retry.py`** — failure-kind constants, `is_retryable()`, `backoff()`. Pure, no I/O.
- **Modify `forge/config.py`** — add four `FORGE_`-prefixed settings.
- **Modify `forge/models.py`** — add `max_retries`, `available_at`, `failure_kind` to `Task` + `to_row`/`from_row`.
- **Modify `forge/db.py`** — add columns to `SCHEMA` and to the idempotent `ALTER` migration list.
- **Modify `forge/store.py`** — `mark_failed(kind=...)`, `list_pending` gate, `requeue()`, `list_active_tasks()`, `clear_for_retry()`.
- **Modify `forge/zellij/runner.py`** + **`forge/zellij/__init__.py`** — module-level `kill_session()`.
- **Modify `forge/agents/echo.py`**, **`forge/agents/code.py`**, **`forge/agents/__init__.py`** — declare `timeout_seconds`.
- **Modify `forge/coordinator.py`** — config wiring, `_effective_timeout`, `_fail_or_retry`, in-process timeout, `reap_stuck_tasks`, startup/tick wiring.
- **Modify `forge/api/tasks.py`** — `POST /{task_id}/retry`.

Tests live beside existing ones: `tests/test_retry.py` (new), `tests/test_config.py`, `tests/test_models.py`, `tests/test_db.py`, `tests/test_store.py`, `tests/test_zellij_runner.py`, `tests/test_coordinator.py`, `tests/test_api.py`.

---

## Task 1: Config settings

**Files:**
- Modify: `forge/config.py:9-12`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config.py`:

```python
def test_resilience_settings_defaults():
    from forge.config import Settings

    s = Settings()
    assert s.max_retries == 3
    assert s.retry_base_seconds == 60
    assert s.retry_max_seconds == 900
    assert s.default_timeout_seconds == 1800
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_resilience_settings_defaults -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'max_retries'`

- [ ] **Step 3: Add the settings**

In `forge/config.py`, after the `# Coordinator` block (after line 12 `max_concurrent_tasks: int = 2`), add:

```python
    # Task resilience — retries with exponential backoff + execution timeout
    max_retries: int = 3
    retry_base_seconds: int = 60
    retry_max_seconds: int = 900
    default_timeout_seconds: int = 1800
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py::test_resilience_settings_defaults -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add forge/config.py tests/test_config.py
git commit -m "feat: add task-resilience settings (retries, backoff, timeout)"
```

---

## Task 2: Pure retry module (backoff + classification)

**Files:**
- Create: `forge/retry.py`
- Test: `tests/test_retry.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_retry.py`:

```python
from forge import retry


def test_failure_kinds_are_distinct_strings():
    kinds = {retry.TRANSIENT, retry.TIMEOUT, retry.DECLINED, retry.VERIFICATION, retry.TERMINAL}
    assert len(kinds) == 5
    assert retry.TRANSIENT == "transient"
    assert retry.TIMEOUT == "timeout"


def test_only_transient_and_timeout_are_retryable():
    assert retry.is_retryable(retry.TRANSIENT) is True
    assert retry.is_retryable(retry.TIMEOUT) is True
    assert retry.is_retryable(retry.DECLINED) is False
    assert retry.is_retryable(retry.VERIFICATION) is False
    assert retry.is_retryable(retry.TERMINAL) is False
    assert retry.is_retryable(None) is False


def test_backoff_is_capped_exponential():
    # base=60, cap=900 → 60, 120, 240, 480, 900 (capped), 900 ...
    assert retry.backoff(1, base=60, cap=900) == 60
    assert retry.backoff(2, base=60, cap=900) == 120
    assert retry.backoff(3, base=60, cap=900) == 240
    assert retry.backoff(4, base=60, cap=900) == 480
    assert retry.backoff(5, base=60, cap=900) == 900
    assert retry.backoff(6, base=60, cap=900) == 900
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_retry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'forge.retry'`

- [ ] **Step 3: Create the module**

Create `forge/retry.py`:

```python
"""Pure helpers for task resilience: failure classification + backoff math.

No I/O — imported by the coordinator and store to decide whether a failed task
should be retried and how long to wait before the next attempt.
"""

# Failure kinds. Recorded on Task.failure_kind and used to decide retry-ability.
TRANSIENT = "transient"        # unexpected exception in a producing stage
TIMEOUT = "timeout"            # stage exceeded its timeout (in-process or reaper)
DECLINED = "declined"          # triage gate returned False — deliberate
VERIFICATION = "verification"  # verify gate returned False — deliberate
TERMINAL = "terminal"          # generic non-retryable failure

_RETRYABLE = frozenset({TRANSIENT, TIMEOUT})


def is_retryable(kind: str | None) -> bool:
    """Only transient exceptions and timeouts are retried automatically."""
    return kind in _RETRYABLE


def backoff(attempt: int, base: int, cap: int) -> int:
    """Seconds to wait before retry number ``attempt`` (1-indexed).

    Exponential: base * 2**(attempt-1), capped at ``cap``.
    attempt=1 → base, attempt=2 → 2*base, ...
    """
    return min(base * (2 ** (attempt - 1)), cap)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_retry.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add forge/retry.py tests/test_retry.py
git commit -m "feat: add pure retry module (failure kinds + capped backoff)"
```

---

## Task 3: Task model fields

**Files:**
- Modify: `forge/models.py:46` (add fields), `forge/models.py:75-93` (`to_row`), `forge/models.py:95-120` (`from_row`)
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_models.py`:

```python
def test_task_resilience_fields_default_and_roundtrip():
    from datetime import datetime, timezone
    from forge.models import Task, TaskSource, TaskType

    task = Task.new(
        task_type=TaskType.ECHO,
        source=TaskSource.CHAT,
        title="t",
        description="d",
    )
    # Defaults
    assert task.max_retries == 3
    assert task.available_at is None
    assert task.failure_kind is None

    # Round-trip through to_row/from_row with non-default values
    task = task.model_copy(update={
        "max_retries": 5,
        "available_at": datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc),
        "failure_kind": "timeout",
    })
    restored = Task.from_row(task.to_row())
    assert restored.max_retries == 5
    assert restored.available_at == task.available_at
    assert restored.failure_kind == "timeout"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py::test_task_resilience_fields_default_and_roundtrip -v`
Expected: FAIL — `Task` has no field `max_retries` (Pydantic ignores the update / attribute error on assert).

- [ ] **Step 3: Add the fields**

In `forge/models.py`, change the field block (currently line 46) from:

```python
    retries: int = 0
    created_at: datetime
```

to:

```python
    retries: int = 0
    max_retries: int = 3
    available_at: datetime | None = None
    failure_kind: str | None = None
    created_at: datetime
```

In `to_row`, add these keys inside the returned dict, right after the `"retries": self.retries,` line:

```python
            "max_retries": self.max_retries,
            "available_at": (
                self.available_at.isoformat() if self.available_at else None
            ),
            "failure_kind": self.failure_kind,
```

In `from_row`, add these keyword args to the `cls(...)` call, right after `retries=row["retries"],`:

```python
            max_retries=row.get("max_retries", 3),
            available_at=(
                datetime.fromisoformat(row["available_at"])
                if row.get("available_at")
                else None
            ),
            failure_kind=row.get("failure_kind"),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py::test_task_resilience_fields_default_and_roundtrip -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add forge/models.py tests/test_models.py
git commit -m "feat: add max_retries/available_at/failure_kind to Task model"
```

---

## Task 4: Database schema + migration

**Files:**
- Modify: `forge/db.py:4-19` (`SCHEMA`), `forge/db.py:109-111` (ALTER list)
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_db.py`:

```python
async def test_tasks_table_has_resilience_columns():
    from forge.db import Database

    db = Database(":memory:")
    await db.initialize()
    try:
        rows = await db.fetch_all("PRAGMA table_info(tasks)")
        names = {r["name"] for r in rows}
        assert {"max_retries", "available_at", "failure_kind"} <= names
    finally:
        await db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_db.py::test_tasks_table_has_resilience_columns -v`
Expected: FAIL — columns missing from the set.

- [ ] **Step 3: Add columns to schema + migration**

In `forge/db.py`, in the `tasks` `CREATE TABLE`, change:

```python
    retries INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
```

to:

```python
    retries INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    available_at TEXT,
    failure_kind TEXT,
    created_at TEXT NOT NULL,
```

Then extend the idempotent ALTER tuple (currently just `tool_use_id`) so pre-existing DBs gain the columns:

```python
        for alter in (
            "ALTER TABLE thread_messages ADD COLUMN tool_use_id TEXT",
            "ALTER TABLE tasks ADD COLUMN max_retries INTEGER NOT NULL DEFAULT 3",
            "ALTER TABLE tasks ADD COLUMN available_at TEXT",
            "ALTER TABLE tasks ADD COLUMN failure_kind TEXT",
        ):
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_db.py::test_tasks_table_has_resilience_columns -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add forge/db.py tests/test_db.py
git commit -m "feat: add resilience columns to tasks table + migration"
```

---

## Task 5: Store — failure kind, backoff gate, requeue, active list, clear-for-retry

**Files:**
- Modify: `forge/store.py:48-53` (`list_pending`), `forge/store.py:106-116` (`mark_failed`), and add new methods after `mark_failed`.
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_store.py`. The file already defines `db` and `store` fixtures and already imports `Task, TaskSource, TaskStatus, TaskType` at the top — only add the `datetime` import if it is not already present:

```python
from datetime import datetime, timedelta, timezone


def _new_task() -> Task:
    return Task.new(
        task_type=TaskType.ECHO, source=TaskSource.CHAT, title="t", description="d"
    )


async def test_mark_failed_records_kind(store):
    task = _new_task()
    await store.save(task)
    await store.mark_failed(task.id, error="boom", kind="transient")
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.FAILED
    assert loaded.failure_kind == "transient"
    assert loaded.handler_data["error"] == "boom"


async def test_list_pending_excludes_future_available_at(store):
    future = _new_task()
    await store.save(future)
    await store.requeue(
        future.id,
        retries=1,
        available_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        error="retry me",
        kind="transient",
    )
    ready = _new_task()
    await store.save(ready)

    pending = await store.list_pending(limit=10)
    ids = {t.id for t in pending}
    assert ready.id in ids
    assert future.id not in ids


async def test_requeue_sets_status_retries_and_kind(store):
    task = _new_task()
    await store.save(task)
    await store.requeue(
        task.id, retries=2, available_at=None, error="e", kind="timeout"
    )
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.QUEUED
    assert loaded.retries == 2
    assert loaded.failure_kind == "timeout"


async def test_list_active_tasks_returns_only_active(store):
    queued = _new_task()
    await store.save(queued)
    executing = _new_task()
    await store.save(executing)
    await store.update_status(executing.id, TaskStatus.EXECUTING)

    active = await store.list_active_tasks()
    ids = {t.id for t in active}
    assert executing.id in ids
    assert queued.id not in ids


async def test_clear_for_retry_resets_budget(store):
    task = _new_task()
    await store.save(task)
    await store.requeue(
        task.id, retries=3, available_at="2099-01-01T00:00:00+00:00", kind="timeout"
    )
    await store.mark_failed(task.id, error="dead", kind="timeout")

    await store.clear_for_retry(task.id)
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.QUEUED
    assert loaded.retries == 0
    assert loaded.available_at is None
    assert loaded.failure_kind is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_store.py -k "kind or available_at or requeue or active or clear_for_retry" -v`
Expected: FAIL — `mark_failed() got an unexpected keyword argument 'kind'` / `AttributeError: 'TaskStore' object has no attribute 'requeue'`.

- [ ] **Step 3: Update `list_pending` to honor the backoff gate**

In `forge/store.py`, replace the body of `list_pending` (lines 48-53) with:

```python
    async def list_pending(self, limit: int = 10) -> list[Task]:
        now = datetime.now(timezone.utc).isoformat()
        rows = await self._db.fetch_all(
            "SELECT * FROM tasks WHERE status = ? "
            "AND (available_at IS NULL OR available_at <= ?) "
            "ORDER BY created_at ASC LIMIT ?",
            (TaskStatus.QUEUED.value, now, limit),
        )
        return [Task.from_row(row) for row in rows]
```

- [ ] **Step 4: Update `mark_failed` to record the kind**

Replace `mark_failed` (lines 106-116) with:

```python
    async def mark_failed(self, task_id: str, error: str, kind: str = "terminal"):
        now = datetime.now(timezone.utc).isoformat()
        task = await self.get(task_id)
        if task is None:
            return
        handler_data = task.handler_data
        handler_data["error"] = error
        await self._db.execute(
            "UPDATE tasks SET status = ?, failure_kind = ?, handler_data = ?, "
            "updated_at = ? WHERE id = ?",
            (TaskStatus.FAILED.value, kind, json.dumps(handler_data), now, task_id),
        )
```

- [ ] **Step 5: Add `requeue`, `list_active_tasks`, `clear_for_retry`**

Immediately after `mark_failed`, add:

```python
    async def requeue(
        self,
        task_id: str,
        retries: int,
        available_at: str | None,
        error: str | None = None,
        kind: str | None = None,
    ):
        """Put a failed task back in the queue with an updated retry count and
        an optional backoff gate (``available_at`` ISO timestamp, or None to run
        immediately)."""
        now = datetime.now(timezone.utc).isoformat()
        task = await self.get(task_id)
        if task is None:
            return
        handler_data = task.handler_data
        if error is not None:
            handler_data["error"] = error
        await self._db.execute(
            "UPDATE tasks SET status = ?, retries = ?, available_at = ?, "
            "failure_kind = ?, handler_data = ?, updated_at = ? WHERE id = ?",
            (
                TaskStatus.QUEUED.value,
                retries,
                available_at,
                kind,
                json.dumps(handler_data),
                now,
                task_id,
            ),
        )

    async def list_active_tasks(self) -> list[Task]:
        """Tasks currently in a non-terminal active state. Used by the reaper."""
        active_states = (
            TaskStatus.TRIAGING.value,
            TaskStatus.EXECUTING.value,
            TaskStatus.VERIFYING.value,
            TaskStatus.DELIVERING.value,
        )
        placeholders = ", ".join("?" for _ in active_states)
        rows = await self._db.fetch_all(
            f"SELECT * FROM tasks WHERE status IN ({placeholders})",
            active_states,
        )
        return [Task.from_row(row) for row in rows]

    async def clear_for_retry(self, task_id: str):
        """Manual retry: reset the retry budget and backoff gate, requeue now."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "UPDATE tasks SET status = ?, retries = 0, available_at = NULL, "
            "failure_kind = NULL, updated_at = ? WHERE id = ?",
            (TaskStatus.QUEUED.value, now, task_id),
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_store.py -k "kind or available_at or requeue or active or clear_for_retry" -v`
Expected: PASS (5 tests)

- [ ] **Step 7: Commit**

```bash
git add forge/store.py tests/test_store.py
git commit -m "feat: store support for failure kinds, backoff gate, requeue, reaper list"
```

---

## Task 6: ZellijRunner.kill_session

**Files:**
- Modify: `forge/zellij/runner.py` (add module-level function at end), `forge/zellij/__init__.py` (export it)
- Test: `tests/test_zellij_runner.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_zellij_runner.py`:

```python
async def test_kill_session_noop_when_zellij_missing(monkeypatch):
    import forge.zellij.runner as runner

    # Simulate zellij not installed — must be a silent no-op, not an error.
    monkeypatch.setattr(runner.shutil, "which", lambda _: None)
    await runner.kill_session("agent-doesnotexist")  # should not raise


async def test_kill_session_invokes_zellij(monkeypatch):
    import forge.zellij.runner as runner

    calls = []

    class FakeProc:
        async def wait(self):
            return 0

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        return FakeProc()

    monkeypatch.setattr(runner.shutil, "which", lambda _: "/usr/bin/zellij")
    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", fake_exec)

    await runner.kill_session("agent-123")
    assert calls and calls[0][:3] == ("zellij", "kill-session", "agent-123")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_zellij_runner.py -k kill_session -v`
Expected: FAIL — `module 'forge.zellij.runner' has no attribute 'kill_session'`.

- [ ] **Step 3: Add the function**

At the end of `forge/zellij/runner.py`, add:

```python
async def kill_session(session_name: str) -> None:
    """Tear down a Zellij session by name. Tolerant of an already-gone session
    and of zellij not being installed (tests/CI) — never raises."""
    if shutil.which("zellij") is None:
        return
    try:
        proc = await asyncio.create_subprocess_exec(
            "zellij",
            "kill-session",
            session_name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    except Exception:
        logger.warning("Failed to kill zellij session %s", session_name, exc_info=True)
```

- [ ] **Step 4: Export it**

In `forge/zellij/__init__.py`, add `kill_session` to the import and `__all__`. The file currently exports `ZellijRunner`; make it match this shape (adjust to the existing import line):

```python
from forge.zellij.runner import ZellijRunner, kill_session

__all__ = ["ZellijRunner", "kill_session"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_zellij_runner.py -k kill_session -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add forge/zellij/runner.py forge/zellij/__init__.py tests/test_zellij_runner.py
git commit -m "feat: add kill_session() for tearing down orphaned zellij sessions"
```

---

## Task 7: Agents declare timeout_seconds

**Files:**
- Modify: `forge/agents/echo.py`, `forge/agents/code.py:42-51` (class attrs), `forge/agents/__init__.py` (Protocol annotation)
- Test: `tests/test_agents.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agents.py`:

```python
def test_agents_declare_timeout_seconds():
    from forge.agents.echo import EchoAgent
    from forge.agents.code import CodeAgent

    assert EchoAgent().timeout_seconds == 60
    assert CodeAgent().timeout_seconds == 3600
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_agents.py::test_agents_declare_timeout_seconds -v`
Expected: FAIL — `'EchoAgent' object has no attribute 'timeout_seconds'`.

- [ ] **Step 3: Declare the attribute on both agents**

In `forge/agents/echo.py`, add a `timeout_seconds` class attribute after `connectors`:

```python
class EchoAgent(Agent):
    name = "echo"
    task_type = "echo"
    stages = ["execute"]
    connectors: list[str] = []
    timeout_seconds = 60
```

In `forge/agents/code.py`, add it after the `connectors = [...]` line in the class body (it sits alongside `name`/`task_type`/`stages`/`connectors`, before `__init__`):

```python
    connectors = ["github", "onepassword"]
    timeout_seconds = 3600
```

- [ ] **Step 4: Document it on the Protocol**

In `forge/agents/__init__.py`, in the `Agent` Protocol attribute block (currently `name`/`task_type`/`stages`/`connectors`), add an optional annotation so the contract is discoverable. Add after `connectors: list[str]`:

```python
    # Optional: max wall-clock seconds for a producing stage before the
    # coordinator times the task out. Falls back to FORGE_DEFAULT_TIMEOUT_SECONDS
    # when an agent does not declare it.
    timeout_seconds: int
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_agents.py::test_agents_declare_timeout_seconds -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add forge/agents/echo.py forge/agents/code.py forge/agents/__init__.py tests/test_agents.py
git commit -m "feat: agents declare per-stage timeout_seconds"
```

---

## Task 8: Coordinator — classification, auto-retry, session teardown

This is the core wiring. We add config/helpers, then route every failure path through `_fail_or_retry`.

**Files:**
- Modify: `forge/coordinator.py` (imports, `__init__`, helpers, `process_pending`)
- Test: `tests/test_coordinator.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_coordinator.py` (the file already has `db`, `store`, `registry`, `coordinator` fixtures):

```python
from unittest.mock import patch


class BoomAgent:
    name = "boom"
    task_type = "boom"
    stages = ["execute"]
    connectors: list[str] = []
    timeout_seconds = 60

    async def execute(self, task, ctx):
        raise RuntimeError("kaboom")


class SlowAgent:
    name = "slow"
    task_type = "slow"
    stages = ["execute"]
    connectors: list[str] = []
    timeout_seconds = 60

    async def execute(self, task, ctx):
        import asyncio
        await asyncio.sleep(5)
        return {}


async def _save(store, type_):
    t = Task.new(task_type=TaskType.ECHO, source=TaskSource.CHAT, title="t", description="d")
    t = t.model_copy(update={"type": type_})
    await store.save(t)
    return t


async def test_transient_exception_requeues_with_backoff(store):
    reg = AgentRegistry()
    reg.register(BoomAgent())
    coord = Coordinator(store=store, registry=reg, max_concurrent=2)

    task = await _save(store, "boom")
    await coord.process_pending()

    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.QUEUED       # requeued, not failed
    assert loaded.retries == 1
    assert loaded.failure_kind == "transient"
    assert loaded.available_at is not None          # backoff gate set


async def test_retries_exhaust_to_terminal_failure(store):
    reg = AgentRegistry()
    reg.register(BoomAgent())
    coord = Coordinator(store=store, registry=reg, max_concurrent=2)

    task = await _save(store, "boom")
    # max_retries default 3 → fails on attempts producing retries 1,2,3 then terminal.
    # Clear the backoff gate before each loop so the task is dequeuable, and stop
    # once it has reached the terminal FAILED state.
    for _ in range(5):
        current = await store.get(task.id)
        if current.status == TaskStatus.FAILED:
            break
        await store._db.execute(
            "UPDATE tasks SET available_at = NULL WHERE id = ?", (task.id,)
        )
        await coord.process_pending()

    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.FAILED
    assert loaded.retries == 3
    assert loaded.failure_kind == "transient"


async def test_timeout_classified_and_requeued(store):
    reg = AgentRegistry()
    reg.register(SlowAgent())
    # default_timeout via settings None → falls back to 1800; override per-task instead.
    coord = Coordinator(store=store, registry=reg, max_concurrent=2)

    task = await _save(store, "slow")
    # Per-task override to force a fast timeout.
    await store.update_handler_data(task.id, {"timeout_seconds": 0.05})
    await coord.process_pending()

    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.QUEUED
    assert loaded.failure_kind == "timeout"


async def test_code_task_session_killed_before_retry(store):
    reg = AgentRegistry()
    reg.register(BoomAgent())
    coord = Coordinator(store=store, registry=reg, max_concurrent=2)

    task = await _save(store, "boom")
    await store.update_handler_data(task.id, {"zellij_session": "agent-x"})

    with patch("forge.coordinator.kill_session") as mock_kill:
        await coord.process_pending()
        mock_kill.assert_awaited_once_with("agent-x")
```

Note: in `test_retries_exhaust_to_terminal_failure`, delete the stray `await store.update_status` line if your linter objects — it is only there to illustrate; the real driver is the `UPDATE ... available_at = NULL` + `process_pending()` loop. (When implementing, simplify that test body to just the loop.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_coordinator.py -k "transient or exhaust or timeout_classified or session_killed" -v`
Expected: FAIL — tasks land in `FAILED` (not `QUEUED`), `failure_kind` is `None`/`terminal`, and `kill_session` is not imported.

- [ ] **Step 3: Add imports + config wiring + helpers**

In `forge/coordinator.py`, update imports near the top:

```python
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from forge import retry
from forge.zellij import kill_session
```

(Keep the existing `from forge.models ...`, `from forge.state ...`, `from forge.store ...`, metrics, agents, connectors imports.)

In `Coordinator.__init__`, after `self._orchestrator = orchestrator`, add config resolution (works whether or not `settings` is passed):

```python
        # Resilience config — read from settings with safe fallbacks for tests
        # that construct the coordinator without a Settings object.
        self._max_retries = getattr(settings, "max_retries", 3) if settings else 3
        self._retry_base = getattr(settings, "retry_base_seconds", 60) if settings else 60
        self._retry_cap = getattr(settings, "retry_max_seconds", 900) if settings else 900
        self._default_timeout = (
            getattr(settings, "default_timeout_seconds", 1800) if settings else 1800
        )
```

Add two helper methods to the class (place them just before `process_pending`):

```python
    def _effective_timeout(self, task: Task, agent) -> float:
        """Resolve the timeout for a producing stage: per-task override →
        agent default → global default."""
        override = (task.handler_data or {}).get("timeout_seconds")
        if override:
            return float(override)
        return float(getattr(agent, "timeout_seconds", None) or self._default_timeout)

    async def _fail_or_retry(self, task: Task, error: str, kind: str) -> None:
        """Single funnel for every failure. Tears down any orphaned Zellij
        session, then requeues with backoff (retryable + budget left) or marks
        the task terminally failed."""
        session = (task.handler_data or {}).get("zellij_session")
        if session:
            try:
                await kill_session(session)
            except Exception:
                logger.exception("kill_session failed for %s", session)

        if retry.is_retryable(kind) and task.retries < self._max_retries:
            next_attempt = task.retries + 1
            delay = retry.backoff(next_attempt, self._retry_base, self._retry_cap)
            available_at = (
                datetime.now(timezone.utc) + timedelta(seconds=delay)
            ).isoformat()
            await self._store.requeue(
                task.id,
                retries=next_attempt,
                available_at=available_at,
                error=error,
                kind=kind,
            )
            logger.info(
                "Requeued task %s (attempt %d/%d, kind=%s, backoff=%ss)",
                task.id, next_attempt, self._max_retries, kind, delay,
            )
        else:
            await self._store.mark_failed(task.id, error=error, kind=kind)
            TASKS_TOTAL.labels(type=task.type, status="failed").inc()
```

- [ ] **Step 4: Route `process_pending` failure paths through the helper**

In `process_pending`, make these four changes inside the `for task in pending:` loop:

(a) The **no-agent** branch (currently `await self._store.mark_failed(...)` + `TASKS_TOTAL...inc()`): replace those two lines with:

```python
                await self._fail_or_retry(
                    task,
                    error=f"No agent registered for type '{task.type}'",
                    kind=retry.TERMINAL,
                )
                tasks_processed += 1
                continue
```

(b) The **triage decline** branch (the `if not ok:` block): replace its `mark_failed` + `TASKS_TOTAL` lines with:

```python
                        reloaded = await self._store.get(task.id)
                        reason = None
                        if reloaded is not None:
                            reason = (reloaded.handler_data or {}).get("triage_reason")
                        await self._fail_or_retry(
                            task,
                            error=reason or "Agent declined task during triage",
                            kind=retry.DECLINED,
                        )
                        continue
```

(c) The **verification failure** branch (`if not verified:`): replace with:

```python
                        await self._fail_or_retry(
                            task, error="Verification failed", kind=retry.VERIFICATION
                        )
                        continue
```

(d) The **outer `except Exception`** at the bottom of the loop: replace its body with timeout-aware classification:

```python
            except TimeoutError as e:
                logger.warning("Task %s timed out: %s", task.id, e)
                await self._fail_or_retry(task, error=str(e), kind=retry.TIMEOUT)
                HANDLER_ERRORS_TOTAL.labels(type=task.type).inc()
            except Exception as e:
                logger.exception(f"Error processing task {task.id}")
                await self._fail_or_retry(task, error=str(e), kind=retry.TRANSIENT)
                HANDLER_ERRORS_TOTAL.labels(type=task.type).inc()
            finally:
                ACTIVE_TASKS.dec()
```

(Note: `_fail_or_retry` reloads nothing — it uses the `task` in hand for `retries`/`handler_data`. The `task` variable was refreshed after `execute` via `task = await self._store.get(task.id)`, so `retries` is current.)

- [ ] **Step 5: Wrap the producing stages in `asyncio.wait_for`** (timeout)

Still in `process_pending`, wrap the **execute** call. Replace:

```python
                result = await agent.execute(task, ctx)
```

with:

```python
                result = await asyncio.wait_for(
                    agent.execute(task, ctx),
                    timeout=self._effective_timeout(task, agent),
                )
```

And wrap the **deliver** call. Replace:

```python
                    delivery = await agent.deliver(task, ctx)
```

with:

```python
                    delivery = await asyncio.wait_for(
                        agent.deliver(task, ctx),
                        timeout=self._effective_timeout(task, agent),
                    )
```

(`asyncio.wait_for` raises `asyncio.TimeoutError`, which is `TimeoutError` on Python 3.11+, so the `except TimeoutError` branch from Step 4 catches it.)

- [ ] **Step 6: Run the new tests + the existing coordinator tests**

Run: `uv run pytest tests/test_coordinator.py -v`
Expected: PASS — new resilience tests pass and the pre-existing tests (`test_process_single_task`, `test_process_echo_task`, etc.) still pass. `test_process_single_task` expects a no-agent `code` task to end `FAILED`; since `TERMINAL` is non-retryable, `_fail_or_retry` marks it failed — still green.

- [ ] **Step 7: Commit**

```bash
git add forge/coordinator.py tests/test_coordinator.py
git commit -m "feat: coordinator failure classification, auto-retry, timeout, session teardown"
```

---

## Task 9: Coordinator — reaper (startup + tick backstop)

**Files:**
- Modify: `forge/coordinator.py` (`startup`, `tick`, add `reap_stuck_tasks`), `tests/test_coordinator.py` (fix `FakeStore`)
- Test: `tests/test_coordinator.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_coordinator.py`:

```python
async def test_reaper_requeues_task_past_timeout(store):
    reg = AgentRegistry()
    reg.register(EchoAgent())  # echo timeout_seconds = 60
    coord = Coordinator(store=store, registry=reg, max_concurrent=2)

    task = await _save(store, "echo")
    await store.update_status(task.id, TaskStatus.EXECUTING)
    # Backdate updated_at well past the 60s echo timeout.
    old = "2000-01-01T00:00:00+00:00"
    await store._db.execute(
        "UPDATE tasks SET updated_at = ? WHERE id = ?", (old, task.id)
    )

    reaped = await coord.reap_stuck_tasks()
    assert reaped == 1
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.QUEUED
    assert loaded.failure_kind == "timeout"


async def test_reaper_ignores_fresh_active_task(store):
    reg = AgentRegistry()
    reg.register(EchoAgent())
    coord = Coordinator(store=store, registry=reg, max_concurrent=2)

    task = await _save(store, "echo")
    await store.update_status(task.id, TaskStatus.EXECUTING)  # updated_at = now

    reaped = await coord.reap_stuck_tasks()
    assert reaped == 0
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.EXECUTING
```

Also update the existing `FakeStore` in `test_coordinator_calls_extra_watchers_in_tick` so it satisfies the reaper's new call. Add a `list_active_tasks` method to that class:

```python
    class FakeStore:
        async def list_pending(self, limit):
            return []

        async def reset_active_tasks(self):
            return 0

        async def list_active_tasks(self):
            return []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_coordinator.py -k "reaper or extra_watchers" -v`
Expected: FAIL — `Coordinator` has no attribute `reap_stuck_tasks` (and, once `tick` calls it, the un-updated `FakeStore` would `AttributeError`).

- [ ] **Step 3: Add `reap_stuck_tasks` and wire startup + tick**

In `forge/coordinator.py`, add the method (next to the other helpers):

```python
    async def reap_stuck_tasks(self) -> int:
        """Backstop for tasks orphaned by a crash/restart: any task stuck in an
        active state longer than its effective timeout is routed through the
        same timeout path as an in-process timeout (teardown + retry-or-fail)."""
        now = datetime.now(timezone.utc)
        reaped = 0
        for task in await self._store.list_active_tasks():
            agent = self._registry.get(task.type)
            timeout = (
                self._effective_timeout(task, agent)
                if agent is not None
                else self._default_timeout
            )
            age = (now - task.updated_at).total_seconds()
            if age > timeout:
                await self._fail_or_retry(
                    task,
                    error=f"Task stuck in {task.status} for {int(age)}s "
                    f"(timeout {int(timeout)}s)",
                    kind=retry.TIMEOUT,
                )
                reaped += 1
        return reaped
```

Replace `startup` (lines 64-68) with a version that uses the reaper:

```python
    async def startup(self):
        """Called once on application start. Reaps tasks left active by an
        unclean shutdown, routing them through the retry/backoff path."""
        reaped = await self.reap_stuck_tasks()
        if reaped > 0:
            logger.info("Reaped %d stuck tasks on startup", reaped)
```

In `tick`, add a reaper pass before `process_pending`. Replace:

```python
        result = await self.process_pending()
        TICK_DURATION_SECONDS.observe(time.monotonic() - tick_start)
        return result
```

with:

```python
        try:
            reaped = await self.reap_stuck_tasks()
            if reaped > 0:
                logger.info("Reaped %d stuck tasks", reaped)
        except Exception:
            logger.exception("Error reaping stuck tasks")

        result = await self.process_pending()
        TICK_DURATION_SECONDS.observe(time.monotonic() - tick_start)
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_coordinator.py -v`
Expected: PASS — reaper tests pass; `test_coordinator_calls_extra_watchers_in_tick` passes with the updated `FakeStore`; all prior tests still green.

- [ ] **Step 5: Commit**

```bash
git add forge/coordinator.py tests/test_coordinator.py
git commit -m "feat: reaper for stuck tasks on startup and each tick"
```

---

## Task 10: Manual retry endpoint

**Files:**
- Modify: `forge/api/tasks.py` (imports + new route)
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api.py`. The file's only fixture is `client` (an `AsyncClient` over the real app); tasks are created through the API. To drive a task into `FAILED` we reach the same store the app configured, via `forge.api.tasks.get_store()`:

```python
async def test_manual_retry_requeues_failed_task(client):
    from forge.api.tasks import get_store
    from forge.models import TaskStatus

    create = await client.post(
        "/api/tasks",
        json={"type": "echo", "title": "t", "description": "d"},
    )
    task_id = create.json()["id"]

    store = get_store()
    await store.mark_failed(task_id, error="boom", kind="timeout")

    resp = await client.post(f"/api/tasks/{task_id}/retry")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["retries"] == 0
    assert body["failure_kind"] is None

    loaded = await store.get(task_id)
    assert loaded.status == TaskStatus.QUEUED


async def test_manual_retry_rejects_non_failed(client):
    create = await client.post(
        "/api/tasks",
        json={"type": "echo", "title": "t", "description": "d"},
    )
    task_id = create.json()["id"]  # status queued, not failed

    resp = await client.post(f"/api/tasks/{task_id}/retry")
    assert resp.status_code == 409


async def test_manual_retry_unknown_task_404(client):
    resp = await client.post("/api/tasks/does-not-exist/retry")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api.py -k manual_retry -v`
Expected: FAIL — `404` for the retry path on all three (route not registered), so the requeue/409 assertions fail.

- [ ] **Step 3: Add the endpoint**

In `forge/api/tasks.py`, add the import near the top (after the existing imports):

```python
from forge.zellij import kill_session
```

Then add the route (place it after `create_task`, before `get_task` so the static `/{task_id}/retry` is registered cleanly):

```python
@router.post("/{task_id}/retry")
async def retry_task(task_id: str, request: Request):
    """Manually requeue a FAILED task with a fresh retry budget, running it
    immediately (ignoring backoff). Kills any lingering Zellij session first."""
    store = get_store()
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.FAILED:
        raise HTTPException(
            status_code=409,
            detail=f"Only failed tasks can be retried (status={task.status.value})",
        )

    session = (task.handler_data or {}).get("zellij_session")
    if session:
        await kill_session(session)

    await store.clear_for_retry(task_id)
    updated = await store.get(task_id)
    return await _task_dict(updated, _thread_store(request))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api.py -k manual_retry -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add forge/api/tasks.py tests/test_api.py
git commit -m "feat: POST /api/tasks/{id}/retry for manual requeue"
```

---

## Task 11: Full suite + lint gate

**Files:** none (verification only)

- [ ] **Step 1: Run the entire backend suite**

Run: `uv run pytest -q`
Expected: PASS — no regressions across the suite (notebook, linear, orchestrator, etc. unaffected).

- [ ] **Step 2: Sanity-check a fresh server boot reaches readiness**

Run: `uv run forge &` then `sleep 3 && curl -s localhost:7030/health && kill %1`
Expected: a healthy response; startup reaper logs `Reaped N stuck tasks on startup` only if applicable, no exceptions.

- [ ] **Step 3: Final commit if anything was touched during verification**

```bash
git add -A
git commit -m "test: verify task-resilience suite green" || echo "nothing to commit"
```

---

## Notes for the implementer

- **DRY:** every failure funnels through `Coordinator._fail_or_retry`. Don't re-implement teardown/requeue logic anywhere else.
- **Retry budget semantics:** `retries` counts attempts already retried. With `max_retries=3` a task runs once, then retries on attempts producing `retries` 1, 2, 3, then fails terminally — 4 executions total.
- **`available_at` is an ISO-8601 UTC string** in the DB; lexical comparison against `datetime.now(timezone.utc).isoformat()` is correct because both use the same fixed format.
- **Timeouts use `asyncio.wait_for`**, which cancels the stage coroutine and frees the slot in-process; the reaper is only a backstop for tasks orphaned across a process restart.
- **Non-retryable kinds** (`declined`, `verification`, `terminal`) still pass through `_fail_or_retry` so session teardown is consistent — they simply skip the requeue branch.
