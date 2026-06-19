# Control Plane Phase 1b — Backend chat/threads teardown

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the now-unused backend chat/threads subsystem (chat + threads APIs, the orchestrator's chat machinery, `ThreadStore`, `post_resolution`, the task↔thread linkage, and the chat/thread DB tables), leaving a lean tasks-centric backend.

**Architecture:** Phase 1a removed all *frontend* references, so nothing calls `/api/chat` or `/api/threads`. This phase removes the backend in dependency order: first strip the two remaining live consumers (the tasks API's thread linkage and the agents API's read of `app.state.orchestrator`), then drop the orchestrator from the coordinator, unwire it all from `main.py`, delete the modules, and drop the dead DB tables — deleting each subsystem's tests in the same commit that invalidates them so the suite stays green throughout.

**Tech Stack:** FastAPI, aiosqlite, pytest. Backend-only; no UI changes.

**Reference — this is the spec:** `docs/superpowers/specs/2026-06-18-dispatch-steer-control-plane-design.md` (the "Removal" section). The `anthropic` SDK dependency must be KEPT (per Thomas; future reuse).

**Scope notes:**
- Backend only. No `ui/` changes.
- `forge/metrics.py` keeps its (now-never-incremented) chat/orchestrator metric series and the `connector="orchestrator"` priming label — harmless dead series, out of scope.
- The physical chat/thread tables on the box's existing DB are left as harmless orphans (the box is nukable); we only remove the schema DDL so fresh DBs don't create them. No destructive `DROP TABLE` migration.

---

### Task 1: Strip thread linkage from the tasks API

`forge/api/tasks.py` still imports `ThreadStore` and enriches task dicts with `origin_thread_id` / `referenced_by_thread_ids`. Remove all of it.

**Files:**
- Modify: `forge/api/tasks.py`
- Modify: `tests/test_api.py` (remove the one thread-filter test)
- Delete: `tests/test_api_threads_enrichment.py`

- [ ] **Step 1: Remove the ThreadStore import and helper**

In `forge/api/tasks.py`:
- Delete the line `from forge.thread_store import ThreadStore`.
- Delete the `_thread_store` helper:
```python
def _thread_store(request: Request) -> ThreadStore | None:
    return getattr(request.app.state, "thread_store", None)
```

- [ ] **Step 2: Simplify `_task_dict` to drop thread enrichment**

Replace:
```python
async def _task_dict(task: Task, thread_store: ThreadStore | None) -> dict:
    out = task.model_dump(mode="json")
    if thread_store is not None:
        out["origin_thread_id"] = await thread_store.origin_thread_for(task.id)
    return out
```
with:
```python
def _task_dict(task: Task) -> dict:
    return task.model_dump(mode="json")
```
(It is now synchronous and takes one argument.)

- [ ] **Step 3: Drop `origin_thread_id` from the request model and create path**

In `CreateTaskRequest`, remove the `origin_thread_id` field and its comment:
```python
    # Optional: link this task to an origin thread at creation time. Used by
    # Forge's task-dispatch turns so the coordinator knows where to post
    # the resolution message on completion.
    origin_thread_id: str | None = None
```
In `create_task`, remove the entire thread-linking block (from `ts = _thread_store(request)` through the `raise HTTPException(... origin_thread_id does not exist ...)`), and change the final return to:
```python
    return _task_dict(task)
```
The coordinator nudge block added in Phase 1a (`if _coordinator is not None and hasattr(_coordinator, "nudge"): _coordinator.nudge()`) stays.

- [ ] **Step 4: Update `retry_task` and `get_task`**

- In `retry_task`, change `return await _task_dict(updated, _thread_store(request))` to `return _task_dict(updated)`.
- In `get_task`, remove the `ts = _thread_store(request)` line and the `referenced_by_thread_ids` enrichment:
```python
    payload = await _task_dict(task, ts)
    if ts is not None:
        payload["referenced_by_thread_ids"] = await ts.referencing_threads(task.id)
    return payload
```
becomes:
```python
    return _task_dict(task)
```

- [ ] **Step 5: Simplify `list_tasks`**

Remove the `origin_thread_id` query parameter and the thread-scoped filter block:
```python
    ts = _thread_store(request)
    # Thread-scoped filter: drop tasks whose origin thread isn't the requested
    # one. ...
    if origin_thread_id and ts is not None:
        filtered: list = []
        for t in tasks:
            origin = await ts.origin_thread_for(t.id)
            if origin == origin_thread_id:
                filtered.append(t)
        tasks = filtered

    return [await _task_dict(t, ts) for t in tasks]
```
becomes:
```python
    return [_task_dict(t) for t in tasks]
```
Also remove `origin_thread_id: str | None = None,` from the `list_tasks` signature. If `Request` is no longer used anywhere in the file, remove it from the FastAPI import; otherwise leave it.

- [ ] **Step 6: Remove the thread-filter test from `tests/test_api.py`**

Delete the entire `test_list_tasks_filter_by_origin_thread` function (it imports `ThreadStore` and exercises the removed filter).

- [ ] **Step 7: Delete the enrichment test file**

```bash
git rm tests/test_api_threads_enrichment.py
```

- [ ] **Step 8: Run tests**

Run: `uv run pytest tests/test_api.py -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add forge/api/tasks.py tests/test_api.py tests/test_api_threads_enrichment.py
git commit -m "refactor(api): drop task<->thread linkage from tasks API"
```

---

### Task 2: Rewire the agents API off the orchestrator

`forge/api/agents.py` reads the agent registry via `app.state.orchestrator.agents`. Expose the registry directly on `app.state` so the agents API survives the orchestrator's removal.

**Files:**
- Modify: `forge/main.py` (set `app.state.agent_registry`)
- Modify: `forge/api/agents.py` (read `app.state.agent_registry`)
- Test: `tests/test_api_agents.py` (new, small)

- [ ] **Step 1: Write a failing test**

Create `tests/test_api_agents.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient

from forge.db import Database
from forge.main import create_app
from forge.agents import AgentRegistry
from forge.agents.echo import EchoAgent


@pytest.fixture
async def client():
    db = Database(":memory:")
    await db.initialize()
    app = create_app(db=db)
    registry = AgentRegistry()
    registry.register(EchoAgent())
    app.state.agent_registry = registry
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await db.close()


async def test_list_agents_reads_from_agent_registry(client):
    resp = await client.get("/api/agents")
    assert resp.status_code == 200
    names = [a["task_type"] for a in resp.json()]
    assert "echo" in names


async def test_get_agent_by_type(client):
    resp = await client.get("/api/agents/echo")
    assert resp.status_code == 200
    assert resp.json()["task_type"] == "echo"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_api_agents.py -v`
Expected: FAIL — currently `_registry` reads `app.state.orchestrator` (unset here), so `/api/agents` returns `[]` and the assertion fails.

- [ ] **Step 3: Point `agents.py` at `app.state.agent_registry`**

In `forge/api/agents.py`, replace `_registry`:
```python
def _registry(request: Request):
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None or orchestrator.agents is None:
        return None
    return orchestrator.agents
```
with:
```python
def _registry(request: Request):
    return getattr(request.app.state, "agent_registry", None)
```

- [ ] **Step 4: Set `app.state.agent_registry` in `main.py`**

In `forge/main.py`, find where the registry is built and agents registered (`registry = AgentRegistry()` … `registry.register(...)`, before the orchestrator). Immediately after the last `registry.register(...)` call for that block (after the Plan/Tickets agents are registered), add:
```python
        app.state.agent_registry = registry
```

- [ ] **Step 5: Run the test**

Run: `uv run pytest tests/test_api_agents.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add forge/api/agents.py forge/main.py tests/test_api_agents.py
git commit -m "refactor(api): agents API reads app.state.agent_registry, not orchestrator"
```

---

### Task 3: Remove the orchestrator from the coordinator

**Files:**
- Modify: `forge/coordinator.py`
- Modify: `forge/main.py` (drop `orchestrator=` from the `Coordinator(...)` call)
- Modify: `forge/agents/__init__.py` (stale docstring)
- Delete: `tests/test_orchestrator_resolution.py`, `tests/test_dispatch_loop.py`

- [ ] **Step 1: Drop the orchestrator constructor param**

In `forge/coordinator.py` `__init__`, remove the `orchestrator=None,` parameter and the `self._orchestrator = orchestrator` assignment.

- [ ] **Step 2: Remove the `post_resolution` block**

In `forge/coordinator.py`, remove the resolution post-back block (and its comment):
```python
                # Post-back resolution to the origin thread, if any. Thread-born
                # tasks get narrated by Forge in the same thread; cron/watcher
                # tasks stay silent and reveal themselves via state.
                reloaded = await self._store.get(task.id)
                if self._orchestrator is not None and reloaded is not None:
                    try:
                        await self._orchestrator.post_resolution(
                            task=reloaded, result=aggregated
                        )
                    except Exception:
                        logger.exception(
                            "Failed to post resolution for task %s", task.id
                        )
```
If `aggregated` or `reloaded` is used by nothing else after this removal, that's fine — leave the surrounding completion/metrics code intact. Do NOT remove the `TASK_DURATION_SECONDS` metric block just above it.

- [ ] **Step 3: Drop `orchestrator=` from the Coordinator construction in `main.py`**

In `forge/main.py`, in the `Coordinator(...)` call, remove the `orchestrator=orchestrator,` keyword argument.

- [ ] **Step 4: Fix the stale docstring in `forge/agents/__init__.py`**

Around line 64 the producer-contract docstring reads:
```
      * ``execute`` and ``deliver`` are **producers**. They return a dict that
        is merged into the task's aggregated result and handed to
        ``orchestrator.post_resolution`` as the widget payload for the
        ``task-resolved`` message. ``execute`` runs first and its dict is the
        base; ``deliver`` runs last and its dict is merged on top.
```
Replace the orchestrator sentence so it reads:
```
      * ``execute`` and ``deliver`` are **producers**. They return a dict that
        is merged into the task's aggregated result (surfaced on the task
        itself). ``execute`` runs first and its dict is the base; ``deliver``
        runs last and its dict is merged on top.
```

- [ ] **Step 5: Delete the resolution/dispatch-loop tests**

```bash
git rm tests/test_orchestrator_resolution.py tests/test_dispatch_loop.py
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_coordinator_nudge.py tests/test_api_dispatch.py -q`
Expected: all pass (the coordinator still constructs and nudges without an orchestrator).

- [ ] **Step 7: Commit**

```bash
git add forge/coordinator.py forge/main.py forge/agents/__init__.py tests/test_orchestrator_resolution.py tests/test_dispatch_loop.py
git commit -m "refactor(coordinator): remove orchestrator post_resolution coupling"
```

---

### Task 4: Unwire chat/threads from `main.py` and remove their HTTP tests

**Files:**
- Modify: `forge/main.py`
- Delete: `tests/test_api_chat.py`, `tests/test_api_threads.py`, `tests/test_chat_dispatch.py`, `tests/test_chat_thread_scoping.py`
- Modify: `tests/test_phase3_dispatchers.py` (drop any chat-dispatch test)

- [ ] **Step 1: Remove module imports**

In `forge/main.py`:
- In the `from forge.api import (...)` tuple, remove `chat,` and `threads as threads_api,`.
- Remove `from forge.orchestrator import ForgeOrchestrator`.
- Remove `from forge.thread_store import ThreadStore`.

- [ ] **Step 2: Remove the router includes**

Remove these two lines:
```python
    app.include_router(chat.router)
    app.include_router(threads_api.router)
```

- [ ] **Step 3: Remove ALL `chat.configure(...)` calls**

There are four `chat.configure(...)` calls in `forge/main.py`; remove every one:
1. `chat.configure(store=store)` — in `create_app`'s `if db is not None:` block.
2. `chat.configure(store=store, connectors=connectors, anthropic_api_key=settings.anthropic_api_key)` — in the lifespan, after connectors are set up.
3. `chat.configure(store=store, connectors=connectors, orchestrator=orchestrator, thread_store=thread_store, anthropic_api_key=settings.anthropic_api_key)` — the orchestrator-wiring call.
4. `chat.configure(store=store, coordinator=coordinator)` — the nudge-wiring call (remove its "Hand the coordinator to chat …" comment too).

After this, verify with `rg -n "chat.configure" forge/main.py` → no matches. The Phase 1a `tasks.set_coordinator(coordinator)` line stays and provides the dispatch nudge.

- [ ] **Step 4: Remove the orchestrator/thread_store construction in the lifespan**

Remove the thread_store + orchestrator construction and wiring (the `chat.configure(...)` calls among them were already removed in Step 3). Concretely remove:
- `thread_store = ThreadStore(db)`
- the `orchestrator = ForgeOrchestrator(...)` construction (the whole multi-line call)
- `app.state.orchestrator = orchestrator`
- `app.state.thread_store = thread_store`

KEEP `memory_store = MemoryStore(settings.memory_dir)` and `app.state.memory_store = memory_store` — used by the MCP server. KEEP `notebook_reader` — it is still passed to `mcp_configure` later, so it must survive even though `ForgeOrchestrator` also consumed it.

- [ ] **Step 6: Delete the chat/threads HTTP + dispatch tests**

```bash
git rm tests/test_api_chat.py tests/test_api_threads.py tests/test_chat_dispatch.py tests/test_chat_thread_scoping.py
```

- [ ] **Step 7: Trim `tests/test_phase3_dispatchers.py`**

Run: `rg -n "chat|/api/chat|orchestrator|thread" tests/test_phase3_dispatchers.py`
Remove any test function that posts to `/api/chat`, imports `forge.api.chat`/`forge.orchestrator`, or exercises chat dispatch. KEEP the cron-schedule and Linear-dispatch tests (they only use `Database`, `TaskStore`, `forge.models`). If the file's only removed-subsystem reference is a docstring mention of "chat repo field" with no actual chat test, leave the tests as-is and just confirm they pass.

- [ ] **Step 8: Verify the app still boots and tests pass**

Run: `uv run python -c "from forge.main import create_app; create_app()"`
Expected: no ImportError/AttributeError.
Run: `uv run pytest tests/test_phase3_dispatchers.py tests/test_api.py -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add forge/main.py tests/
git commit -m "refactor(main): unwire chat/threads/orchestrator from app assembly"
```

---

### Task 5: Delete the chat/threads/orchestrator modules and their unit tests

Nothing references these now. Delete them.

**Files:**
- Delete: `forge/api/chat.py`, `forge/api/threads.py`, `forge/thread_store.py`, `forge/orchestrator/` (whole package)
- Delete: `tests/test_orchestrator.py`, `tests/test_orchestrator_memory.py`, `tests/test_notebook_context.py`, `tests/test_thread_store.py`

- [ ] **Step 1: Confirm no surviving importers**

Run: `rg -n "from forge\.orchestrator|import orchestrator|forge\.thread_store|ThreadStore|api\.chat|api import.*\bchat\b|api import.*threads" forge`
Expected: no matches (only possibly the `from forge.api import (...)` line if Task 4 missed one — if so, fix it before deleting).

- [ ] **Step 2: Delete the modules**

```bash
git rm forge/api/chat.py forge/api/threads.py forge/thread_store.py
git rm -r forge/orchestrator
```

- [ ] **Step 3: Delete the orchestrator/thread unit tests**

```bash
git rm tests/test_orchestrator.py tests/test_orchestrator_memory.py tests/test_notebook_context.py tests/test_thread_store.py
```

- [ ] **Step 4: Verify**

Run: `uv run python -c "from forge.main import create_app; create_app()"`
Expected: no error.
Run: `uv run pytest -q`
Expected: all pass (chat_messages store + DB tables are removed in Task 6; nothing should reference the deleted modules now).

- [ ] **Step 5: Commit**

```bash
git add -A forge tests
git commit -m "refactor: delete chat/threads/orchestrator modules and their tests"
```

---

### Task 6: Remove the `chat_messages` store methods and drop the chat/thread DB tables

**Files:**
- Modify: `forge/store.py` (remove `chat_messages` methods)
- Modify: `forge/db.py` (drop chat/thread DDL + the `tool_use_id` migration)
- Delete: `tests/test_store_chat.py`
- Modify: `tests/test_db.py` (drop the `chat_messages` assertion)

- [ ] **Step 1: Confirm `chat_messages` has no surviving caller**

Run: `rg -n "chat_messages|save_chat_message|list_chat_messages|clear_chat_messages" forge tests`
Expected: matches only in `forge/store.py`, `forge/db.py`, and `tests/test_store_chat.py` (and the `-- supersedes chat_messages` comment in db.py). If anything else references them, stop and report.

- [ ] **Step 2: Remove the chat-message methods from `forge/store.py`**

Remove the three methods (around lines 186–200): the `save_chat_message` (insert into `chat_messages`), `list_chat_messages`, and `clear_chat_messages` methods. Remove only these; leave all task/schedule methods intact.

- [ ] **Step 3: Drop the chat/thread DDL in `forge/db.py`**

In the `SCHEMA` string, remove these `CREATE TABLE`/`CREATE INDEX` blocks entirely:
- `CREATE TABLE IF NOT EXISTS chat_messages (...)`
- the `-- Threads ...` comment + `CREATE TABLE IF NOT EXISTS threads (...)`
- the `-- Thread messages ...` comment + `CREATE TABLE IF NOT EXISTS thread_messages (...)` + its `CREATE INDEX ... thread_messages_thread_id`
- the `-- Task ↔ Thread join ...` comment + `CREATE TABLE IF NOT EXISTS thread_tasks (...)` + its `CREATE INDEX ... thread_tasks_task_id`

KEEP `tasks`, `task_logs`, `schedules`, and `speedtest_results`.

- [ ] **Step 4: Remove the `tool_use_id` migration**

In `Database.initialize`, remove `"ALTER TABLE thread_messages ADD COLUMN tool_use_id TEXT",` from the `for alter in (...)` tuple. KEEP the three `ALTER TABLE tasks ...` migrations.

- [ ] **Step 5: Delete `tests/test_store_chat.py` and trim `tests/test_db.py`**

```bash
git rm tests/test_store_chat.py
```
In `tests/test_db.py`, in `test_initialize_creates_tables`, remove the line `assert "chat_messages" in table_names`. Keep the `tasks`/`task_logs`/`schedules` assertions.

- [ ] **Step 6: Verify**

Run: `uv run pytest tests/test_db.py -q && uv run pytest -q`
Expected: all pass; a fresh in-memory DB initializes with no chat/thread tables.

- [ ] **Step 7: Commit**

```bash
git add forge/store.py forge/db.py tests/test_db.py tests/test_store_chat.py
git commit -m "refactor(db): drop chat/thread tables and chat_messages store methods"
```

---

### Task 7: Final sweep + verification

**Files:** none (verification only)

- [ ] **Step 1: Grep for any dangling references**

Run: `rg -n "thread_store|ThreadStore|ForgeOrchestrator|post_resolution|api\.chat|api\.threads|chat_messages" forge tests`
Expected: no functional references. Acceptable survivors: a comment/docstring in `forge/api/memory.py` or `forge/memory/__init__.py` mentioning "orchestrator" historically, and the `forge/metrics.py` chat/orchestrator metric series (intentionally retained). If any *import* or *call* of a removed symbol remains, fix it.

- [ ] **Step 2: Confirm the MCP server and connectors are untouched**

Run: `rg -n "thread|chat" forge/mcp` 
Expected: no matches (MCP exposed tasks/memory/repos/schedules/notebook/web-search, never chat/threads).

- [ ] **Step 3: App boot smoke**

Run: `uv run python -c "from forge.main import create_app; app = create_app(); print('routes:', len([r for r in app.routes]))"`
Expected: prints a route count, no error. (Optionally confirm no route path starts with `/api/chat` or `/api/threads`.)

- [ ] **Step 4: Full backend suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Confirm the `anthropic` dependency is still present**

Run: `rg -n "anthropic" pyproject.toml`
Expected: `anthropic>=...` still listed (must NOT have been removed).
