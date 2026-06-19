# Control Plane Phase 2a — Steering: states, approval gates, cancel

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the two new pipeline states (`awaiting_approval`, `cancelled`), an opt-in pre-deliver approval gate, and the `cancel`/`approve`/`reject` task endpoints, so an operator can stop a run or gate delivery — all on the existing one-shot execution model.

**Architecture:** A task dispatched with `require_approval=true` runs triage→execute→verify as usual, then the coordinator parks it in `awaiting_approval` instead of delivering. `approve` flips it to `delivering` and nudges the coordinator, which runs a deliver-only resume pass (`resume_approved_deliveries`) reusing an extracted `_deliver_and_complete` helper. `reject` and `cancel` kill any Zellij session and set `cancelled` (terminal). Parked `awaiting_approval` tasks are naturally ignored by the dequeue (`list_pending` selects only `queued`), the reaper, and startup-reset (both list only the four in-flight states), so no changes are needed there.

**Tech Stack:** FastAPI, aiosqlite, pytest. Backend only.

**Reference — this is the spec:** `docs/superpowers/specs/2026-06-18-dispatch-steer-control-plane-design.md` ("Steering API", "Coordinator changes", state model).

**Scope notes:**
- This is **Phase 2a**: the approval gate + cancel/approve/reject. **Follow-up continuation** (`continues_task_id`, `claude --continue`, worktree reuse) is **Phase 2b**; the **task-detail steer controls UI** is **Phase 2c**. The `follow-up` endpoint is NOT built here.
- Accepted edge case: if the box restarts while a task is in `delivering` after approval but before the resume pass runs, startup-reset returns it to `queued` and it re-runs the full pipeline. Approval-gated tasks are opt-in and rare; the box is nukable. Documented, not handled.

---

### Task 1: Add `cancelled` and `awaiting_approval` states + transitions

**Files:**
- Modify: `forge/models.py` (`TaskStatus` enum)
- Modify: `forge/state.py` (`VALID_TRANSITIONS`)
- Test: `tests/test_state.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_state.py`:
```python
import pytest
from forge.models import TaskStatus
from forge.state import transition, InvalidTransition, VALID_TRANSITIONS


def test_verify_can_pause_for_approval():
    assert transition(TaskStatus.VERIFYING, TaskStatus.AWAITING_APPROVAL) == TaskStatus.AWAITING_APPROVAL


def test_approval_resolves_to_delivering_or_cancelled():
    assert transition(TaskStatus.AWAITING_APPROVAL, TaskStatus.DELIVERING) == TaskStatus.DELIVERING
    assert transition(TaskStatus.AWAITING_APPROVAL, TaskStatus.CANCELLED) == TaskStatus.CANCELLED


def test_active_states_can_cancel():
    for s in (
        TaskStatus.QUEUED,
        TaskStatus.TRIAGING,
        TaskStatus.EXECUTING,
        TaskStatus.VERIFYING,
        TaskStatus.DELIVERING,
        TaskStatus.AWAITING_APPROVAL,
    ):
        assert transition(s, TaskStatus.CANCELLED) == TaskStatus.CANCELLED


def test_cancelled_is_terminal():
    assert VALID_TRANSITIONS[TaskStatus.CANCELLED] == set()


def test_execute_can_pause_for_approval_when_no_verify():
    assert transition(TaskStatus.EXECUTING, TaskStatus.AWAITING_APPROVAL) == TaskStatus.AWAITING_APPROVAL


def test_illegal_transition_still_raises():
    with pytest.raises(InvalidTransition):
        transition(TaskStatus.COMPLETED, TaskStatus.DELIVERING)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_state.py -v`
Expected: FAIL — `AttributeError: AWAITING_APPROVAL` / `CANCELLED` not on `TaskStatus`.

- [ ] **Step 3: Add the enum members**

In `forge/models.py`, in `TaskStatus`, add two members after `FAILED`:
```python
class TaskStatus(StrEnum):
    QUEUED = "queued"
    TRIAGING = "triaging"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    DELIVERING = "delivering"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"
    CANCELLED = "cancelled"
```

- [ ] **Step 4: Extend the transition table**

In `forge/state.py`, update `VALID_TRANSITIONS`. Add `AWAITING_APPROVAL` and `CANCELLED` as targets on the pre-deliver states, add the two new states' own rows, and allow `CANCELLED` from every active state:
```python
VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.QUEUED: {
        TaskStatus.TRIAGING,
        TaskStatus.EXECUTING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.TRIAGING: {
        TaskStatus.EXECUTING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.EXECUTING: {
        TaskStatus.VERIFYING,
        TaskStatus.DELIVERING,
        TaskStatus.COMPLETED,
        TaskStatus.AWAITING_APPROVAL,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.VERIFYING: {
        TaskStatus.DELIVERING,
        TaskStatus.COMPLETED,
        TaskStatus.AWAITING_APPROVAL,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.DELIVERING: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.AWAITING_APPROVAL: {
        TaskStatus.DELIVERING,
        TaskStatus.CANCELLED,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: {TaskStatus.QUEUED},
    TaskStatus.CANCELLED: set(),
}
```

- [ ] **Step 5: Run the test**

Run: `uv run pytest tests/test_state.py -v`
Expected: PASS.

- [ ] **Step 6: Run the broader suite to confirm no transition regressions**

Run: `uv run pytest tests/test_coordinator.py -q`
Expected: all pass (existing transitions unchanged; only additions).

- [ ] **Step 7: Commit**

```bash
git add forge/models.py forge/state.py tests/test_state.py
git commit -m "feat(state): add awaiting_approval + cancelled states and transitions"
```

---

### Task 2: Add `require_approval` to the Task model + DB column

**Files:**
- Modify: `forge/models.py` (`Task` model: field, `new()`, `to_row`, `from_row`)
- Modify: `forge/db.py` (schema column + migration)
- Test: `tests/test_db.py` (round-trip assertion)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_db.py`:
```python
async def test_task_require_approval_roundtrips(store):
    from forge.models import Task, TaskType, TaskSource, TaskStatus
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.MANUAL,
        title="gated",
        description="needs approval",
        require_approval=True,
    )
    await store.save(task)
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.require_approval is True
```
(If `tests/test_db.py` has no `store` fixture, use the `store` fixture from `tests/conftest.py` — confirm it exists with `rg -n "def store" tests/conftest.py`; it does.)

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_db.py::test_task_require_approval_roundtrips -v`
Expected: FAIL — `Task.new()` got an unexpected keyword argument `require_approval` (or the attribute is missing on the loaded task).

- [ ] **Step 3: Add the model field**

In `forge/models.py`, in the `Task` model field block (near `max_retries`/`available_at`/`failure_kind`), add:
```python
    require_approval: bool = False
```
In `Task.new(...)`, add a parameter `require_approval: bool = False,` and pass it into the constructed Task (set `require_approval=require_approval`).

- [ ] **Step 4: Persist it in `to_row` and `from_row`**

In `to_row` (the dict that includes `"max_retries"`, `"available_at"`, `"failure_kind"`), add:
```python
            "require_approval": int(self.require_approval),
```
In `from_row` (where it reads `max_retries=row.get("max_retries", 3)` etc.), add:
```python
            require_approval=bool(row.get("require_approval", 0)),
```

- [ ] **Step 5: Add the DB column + migration**

In `forge/db.py`, in the `CREATE TABLE IF NOT EXISTS tasks (...)` block, add a column after `failure_kind TEXT,`:
```python
    require_approval INTEGER NOT NULL DEFAULT 0,
```
And in `Database.initialize`, add to the `for alter in (...)` migration tuple:
```python
            "ALTER TABLE tasks ADD COLUMN require_approval INTEGER NOT NULL DEFAULT 0",
```

- [ ] **Step 6: Confirm `save` writes the new column**

Run: `rg -n "INSERT INTO tasks|to_row" forge/store.py` and confirm `save` uses `task.to_row()` (it builds the INSERT from the row dict). If `save` hardcodes a column list instead of using `to_row()` keys, add `require_approval` to that INSERT and its values. Read `forge/store.py:12` (the `save` method) to verify.

- [ ] **Step 7: Run the test**

Run: `uv run pytest tests/test_db.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add forge/models.py forge/db.py tests/test_db.py
git commit -m "feat(model): add require_approval to Task + DB column"
```

---

### Task 3: Accept `require_approval` on `POST /api/tasks`

**Files:**
- Modify: `forge/api/tasks.py` (`CreateTaskRequest` + `create_task`)
- Test: `tests/test_api_dispatch.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api_dispatch.py`:
```python
async def test_create_task_with_require_approval(client):
    c, store, nudged = client
    resp = await c.post(
        "/api/tasks",
        json={
            "type": "code",
            "title": "gated",
            "description": "needs sign-off",
            "repo": "t-eckert/x",
            "require_approval": True,
        },
    )
    assert resp.status_code == 201
    saved = await store.get(resp.json()["id"])
    assert saved is not None and saved.require_approval is True
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_api_dispatch.py::test_create_task_with_require_approval -v`
Expected: FAIL — `require_approval` ignored (saved task has it False).

- [ ] **Step 3: Add the field + pass it through**

In `forge/api/tasks.py`, in `CreateTaskRequest`, add:
```python
    require_approval: bool = False
```
In `create_task`, pass it into `Task.new(...)`:
```python
        require_approval=req.require_approval,
```

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/test_api_dispatch.py -q`
Expected: PASS (both dispatch tests).

- [ ] **Step 5: Commit**

```bash
git add forge/api/tasks.py tests/test_api_dispatch.py
git commit -m "feat(api): accept require_approval on POST /api/tasks"
```

---

### Task 4: Store methods for cancel + approve

**Files:**
- Modify: `forge/store.py`
- Test: `tests/test_store_steering.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_store_steering.py`:
```python
import pytest
from forge.models import Task, TaskType, TaskSource, TaskStatus


async def _make(store, status=TaskStatus.AWAITING_APPROVAL):
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d")
    await store.save(task)
    await store.update_status(task.id, status)
    return task.id


async def test_mark_cancelled_sets_status(store):
    tid = await _make(store, TaskStatus.EXECUTING)
    await store.mark_cancelled(tid)
    loaded = await store.get(tid)
    assert loaded.status == TaskStatus.CANCELLED


async def test_mark_approved_sets_delivering(store):
    tid = await _make(store, TaskStatus.AWAITING_APPROVAL)
    await store.mark_approved(tid)
    loaded = await store.get(tid)
    assert loaded.status == TaskStatus.DELIVERING
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_store_steering.py -v`
Expected: FAIL — `mark_cancelled` / `mark_approved` not defined.

- [ ] **Step 3: Add the store methods**

In `forge/store.py`, near `mark_completed`/`mark_failed`, add:
```python
    async def mark_cancelled(self, task_id: str):
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (TaskStatus.CANCELLED.value, now, task_id),
        )

    async def mark_approved(self, task_id: str):
        """Flip an awaiting_approval task to delivering so the coordinator's
        resume pass finishes its deliver stage."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (TaskStatus.DELIVERING.value, now, task_id),
        )
```

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/test_store_steering.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/store.py tests/test_store_steering.py
git commit -m "feat(store): mark_cancelled + mark_approved"
```

---

### Task 5: Coordinator — park before deliver when `require_approval`

Extract the deliver+complete+Linear-post logic into a reusable helper, then add the approval gate that parks the task in `awaiting_approval` instead of delivering.

**Files:**
- Modify: `forge/coordinator.py`
- Test: `tests/test_coordinator_steering.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_coordinator_steering.py`:
```python
import pytest
from forge.coordinator import Coordinator
from forge.agents import AgentRegistry
from forge.models import Task, TaskType, TaskSource, TaskStatus
from forge.store import TaskStore
from forge.db import Database


class FullAgent:
    """execute + verify + deliver, all trivial."""
    name = "full"
    task_type = "code"
    stages = ["execute", "verify", "deliver"]
    connectors: list = []

    async def execute(self, task, ctx):
        return {"executed": True}

    async def verify(self, task, ctx):
        return True

    async def deliver(self, task, ctx):
        return {"delivered": True}


@pytest.fixture
async def setup():
    db = Database(":memory:")
    await db.initialize()
    store = TaskStore(db)
    registry = AgentRegistry()
    registry.register(FullAgent())
    coord = Coordinator(store=store, registry=registry, connectors=None, settings=None, max_concurrent=2)
    yield store, coord
    await db.close()


async def test_require_approval_parks_before_deliver(setup):
    store, coord = setup
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d", require_approval=True)
    await store.save(task)
    await coord.process_pending()
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.AWAITING_APPROVAL
    # deliver did NOT run
    assert "delivered" not in (loaded.handler_data or {})


async def test_no_approval_completes_normally(setup):
    store, coord = setup
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d")
    await store.save(task)
    await coord.process_pending()
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.COMPLETED
```
(`FullAgent` registers as task_type "code"; `TaskType.CODE` matches. The registry's `register` may validate that `execute` exists — it does. If `AgentRegistry.register` requires more attributes, mirror the minimal shape used in `tests/test_coordinator.py`'s fake agents — read that file's `_Exec`/`BoomAgent` for the exact required attributes and match them.)

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_coordinator_steering.py -v`
Expected: FAIL on `test_require_approval_parks_before_deliver` — the task completes (status COMPLETED, `delivered` present) because no gate exists yet.

- [ ] **Step 3: Extract a `_deliver_and_complete` helper**

In `forge/coordinator.py`, the deliver+complete+Linear block currently lives inline in `process_pending` (the `if "deliver" in stages:` block through the Linear post-back). Extract it into a method on `Coordinator`:
```python
    async def _deliver_and_complete(self, task, agent, ctx, aggregated: dict) -> None:
        """Run the deliver stage (if the agent has one), mark the task completed
        with the aggregated result, and post the result to Linear if applicable.
        Shared by the normal pipeline and the post-approval resume pass."""
        stages = agent.stages
        if "deliver" in stages:
            new_status = transition(task.status, TaskStatus.DELIVERING)
            await self._store.update_status(task.id, new_status)
            stage_start = time.monotonic()
            delivery = await asyncio.wait_for(
                agent.deliver(task, ctx),
                timeout=self._effective_timeout(task, agent),
            )
            TASK_STAGE_DURATION_SECONDS.labels(stage="deliver").observe(
                time.monotonic() - stage_start
            )
            aggregated = {**aggregated, **(delivery or {})}

        await self._store.mark_completed(task.id, aggregated)
        TASKS_TOTAL.labels(type=task.type, status="completed").inc()

        reloaded = await self._store.get(task.id)
        if self._poller is not None and reloaded is not None:
            try:
                await self._poller.post_result(reloaded)
            except Exception:
                logger.exception("Failed to post Linear result for task %s", task.id)
```
Note: `transition(task.status, ...)` requires `task.status` to be the current status. In the normal flow the in-hand `task` was refreshed after verify; pass the refreshed task. In the resume flow (Task 6) the task is loaded fresh in `awaiting_approval`→`delivering` already, so guard the transition: if `task.status == TaskStatus.DELIVERING` skip the transition call. Adjust the helper to:
```python
        if "deliver" in stages:
            if task.status != TaskStatus.DELIVERING:
                await self._store.update_status(task.id, transition(task.status, TaskStatus.DELIVERING))
            ...
```

- [ ] **Step 4: Replace the inline deliver block + add the gate**

In `process_pending`, replace the inline `if "deliver" in stages:` ... deliver ... `mark_completed` ... Linear block with the gate + helper call. After the verify block and before what was the deliver block, insert:
```python
                # Approval gate — park before deliver if the task opted in.
                if task.require_approval and "deliver" in stages:
                    await self._store.update_status(
                        task.id, transition(current_status, TaskStatus.AWAITING_APPROVAL)
                    )
                    continue

                await self._deliver_and_complete(task, agent, ctx, aggregated)

                TASK_DURATION_SECONDS.labels(type=task.type).observe(
                    time.monotonic() - task_start
                )
```
Remove the old inline deliver/mark_completed/Linear lines (now in the helper). Keep the `TASK_DURATION_SECONDS` observation in the main flow (the helper does not record it). The `current_status` at the gate is `VERIFYING` (verify ran) or `EXECUTING` (no verify) — both have `AWAITING_APPROVAL` as a legal target (Task 1).

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_coordinator_steering.py -v`
Expected: PASS (both).
Run: `uv run pytest tests/test_coordinator.py -q`
Expected: all pass (the refactor preserves normal-flow behavior).

- [ ] **Step 6: Commit**

```bash
git add forge/coordinator.py tests/test_coordinator_steering.py
git commit -m "feat(coordinator): approval gate parks task before deliver"
```

---

### Task 6: Coordinator — resume approved deliveries

**Files:**
- Modify: `forge/coordinator.py` (`tick` + a new `resume_approved_deliveries`)
- Test: `tests/test_coordinator_steering.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_coordinator_steering.py`:
```python
async def test_resume_delivers_approved_task(setup):
    store, coord = setup
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d", require_approval=True)
    await store.save(task)
    await coord.process_pending()  # parks in awaiting_approval
    assert (await store.get(task.id)).status == TaskStatus.AWAITING_APPROVAL

    await store.mark_approved(task.id)  # awaiting_approval -> delivering
    await coord.resume_approved_deliveries()

    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.COMPLETED
    assert loaded.result.get("delivered") is True
```
(`loaded.result` is the completed result dict; confirm `Task.from_row` exposes `result` — read `forge/models.py`. If `result` is stored as a JSON string field named differently, assert via `store.get(...).result` per the model.)

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_coordinator_steering.py::test_resume_delivers_approved_task -v`
Expected: FAIL — `resume_approved_deliveries` not defined.

- [ ] **Step 3: Add `resume_approved_deliveries` and call it in `tick`**

In `forge/coordinator.py`, add:
```python
    async def resume_approved_deliveries(self) -> int:
        """Finish tasks that were approved after an approval-gate pause. Such a
        task sits in `delivering` (set by mark_approved) with its execute/verify
        results already in handler_data; run only its deliver stage + complete.
        The normal pipeline never leaves a task in `delivering` between ticks, so
        this only catches post-approval resumes."""
        resumed = 0
        for task in await self._store.list_by_status(TaskStatus.DELIVERING):
            agent = self._registry.get(task.type)
            if agent is None:
                continue
            ctx = self._build_context(agent)
            aggregated = dict(task.handler_data or {})
            try:
                await self._deliver_and_complete(task, agent, ctx, aggregated)
                resumed += 1
            except Exception:
                logger.exception("Resume-deliver failed for task %s", task.id)
                await self._fail_or_retry(task, error="deliver failed after approval", kind=retry.TERMINAL)
        return resumed
```
In `tick`, call it just before `result = await self.process_pending()`:
```python
        try:
            await self.resume_approved_deliveries()
        except Exception:
            logger.exception("Error resuming approved deliveries")

        result = await self.process_pending()
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_coordinator_steering.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add forge/coordinator.py tests/test_coordinator_steering.py
git commit -m "feat(coordinator): resume deliver after approval"
```

---

### Task 7: `cancel` / `approve` / `reject` endpoints

**Files:**
- Modify: `forge/api/tasks.py`
- Test: `tests/test_api_steering.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_api_steering.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient

from forge.db import Database
from forge.main import create_app
from forge.api import tasks as tasks_api
from forge.store import TaskStore
from forge.models import Task, TaskType, TaskSource, TaskStatus


@pytest.fixture
async def client():
    db = Database(":memory:")
    await db.initialize()
    app = create_app(db=db)
    store = tasks_api.get_store()

    nudged = {"count": 0}

    class StubCoordinator:
        def nudge(self) -> None:
            nudged["count"] += 1

    tasks_api.set_coordinator(StubCoordinator())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, store, nudged
    tasks_api.set_coordinator(None)
    await db.close()


async def _seed(store, status):
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d")
    await store.save(task)
    await store.update_status(task.id, status)
    return task.id


async def test_cancel_running_task(client):
    c, store, _ = client
    tid = await _seed(store, TaskStatus.EXECUTING)
    resp = await c.post(f"/api/tasks/{tid}/cancel")
    assert resp.status_code == 200
    assert (await store.get(tid)).status == TaskStatus.CANCELLED


async def test_cancel_terminal_task_409(client):
    c, store, _ = client
    tid = await _seed(store, TaskStatus.COMPLETED)
    resp = await c.post(f"/api/tasks/{tid}/cancel")
    assert resp.status_code == 409


async def test_approve_sets_delivering_and_nudges(client):
    c, store, nudged = client
    tid = await _seed(store, TaskStatus.AWAITING_APPROVAL)
    resp = await c.post(f"/api/tasks/{tid}/approve")
    assert resp.status_code == 200
    assert (await store.get(tid)).status == TaskStatus.DELIVERING
    assert nudged["count"] == 1


async def test_approve_wrong_state_409(client):
    c, store, _ = client
    tid = await _seed(store, TaskStatus.EXECUTING)
    resp = await c.post(f"/api/tasks/{tid}/approve")
    assert resp.status_code == 409


async def test_reject_cancels(client):
    c, store, _ = client
    tid = await _seed(store, TaskStatus.AWAITING_APPROVAL)
    resp = await c.post(f"/api/tasks/{tid}/reject")
    assert resp.status_code == 200
    assert (await store.get(tid)).status == TaskStatus.CANCELLED


async def test_cancel_unknown_404(client):
    c, _, _ = client
    resp = await c.post("/api/tasks/nonexistent/cancel")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_api_steering.py -v`
Expected: FAIL — endpoints return 404/405 (not defined).

- [ ] **Step 3: Add the endpoints**

In `forge/api/tasks.py`, add after `retry_task`. Note `kill_session` is already imported (`from forge.zellij import kill_session`); `_coordinator` and `_task_dict` already exist from earlier phases.
```python
_TERMINAL = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}


async def _kill_session_if_any(task) -> None:
    session = (task.handler_data or {}).get("zellij_session")
    if session:
        await kill_session(session)


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    store = get_store()
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in _TERMINAL:
        raise HTTPException(status_code=409, detail=f"Cannot cancel a {task.status.value} task")
    await _kill_session_if_any(task)
    await store.mark_cancelled(task_id)
    return _task_dict(await store.get(task_id))


@router.post("/{task_id}/approve")
async def approve_task(task_id: str):
    store = get_store()
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.AWAITING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Only awaiting_approval tasks can be approved (status={task.status.value})")
    await store.mark_approved(task_id)
    if _coordinator is not None and hasattr(_coordinator, "nudge"):
        _coordinator.nudge()
    return _task_dict(await store.get(task_id))


@router.post("/{task_id}/reject")
async def reject_task(task_id: str):
    store = get_store()
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.AWAITING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Only awaiting_approval tasks can be rejected (status={task.status.value})")
    await _kill_session_if_any(task)
    await store.mark_cancelled(task_id)
    return _task_dict(await store.get(task_id))
```
Confirm `TaskStatus` is imported in `forge/api/tasks.py` (it is — used by `retry_task`). If not, add it to the `from forge.models import ...` line.

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/test_api_steering.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add forge/api/tasks.py tests/test_api_steering.py
git commit -m "feat(api): cancel/approve/reject task endpoints"
```

---

### Task 8: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Full backend suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 2: App boot smoke + new routes present**

Run:
```bash
uv run python -c "
from forge.main import create_app
app = create_app()
paths = sorted({getattr(r,'path','') for r in app.routes})
for p in ['/api/tasks/{task_id}/cancel','/api/tasks/{task_id}/approve','/api/tasks/{task_id}/reject']:
    assert p in paths, p
print('steering routes present')
"
```
Expected: prints `steering routes present`, no assertion error.

- [ ] **Step 3: Confirm the gate is opt-in (no behavior change by default)**

Run: `uv run pytest tests/test_coordinator.py tests/test_coordinator_steering.py -q`
Expected: all pass — existing tasks (no `require_approval`) still flow execute→verify→deliver→completed unchanged; only opt-in tasks park.
