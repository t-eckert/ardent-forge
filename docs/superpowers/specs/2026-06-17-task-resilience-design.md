---
title: Task resilience — retries, timeouts, and manual requeue
date: 2026-06-17
status: draft
area: coordinator
---

# Task resilience — retries, timeouts, and manual requeue

## Problem

The task pipeline has no resilience layer. Today:

- `Task.retries` exists but is **never read or written** — a failure is terminal.
- There is **no manual retry**; `api/tasks.py` exposes only create/get/list, even
  though the `FAILED → QUEUED` transition is already legal in `forge/state.py`.
- There is **no execution timeout**. A hung `execute()` holds `ACTIVE_TASKS` and a
  concurrency slot indefinitely. `ZellijRunner` has an internal timeout, but on expiry it
  raises `TimeoutError` **without killing the session** (`runner.py` line ~137), orphaning
  the `agent-<task.id>` Zellij session.
- `reset_active_tasks` recovers stuck tasks **only on startup**, and does so with a blind
  requeue that ignores any retry budget.

The result: transient infrastructure failures (a subprocess dying, a network blip, a
wedged Claude session) are permanently fatal, and wedged sessions can starve the queue.

## Goals

1. Automatically retry failures that are plausibly transient, with backoff.
2. Bound execution time per task and reclaim slots from hung work.
3. Allow a human to requeue a failed task on demand.
4. Clean up orphaned Zellij sessions so retries don't collide with them.

## Decisions (resolved during brainstorming)

- **Retry scope:** auto-retry only **unexpected exceptions** and **timeouts**.
  Triage-declines and verification-failures are deliberate decisions and stay terminal.
- **Timeout config:** **per-agent default** (`timeout_seconds`) with an optional
  **per-task override** via `handler_data["timeout_seconds"]`.
- **Session teardown:** on timeout/reap of a Code task, **kill the session before
  requeue** (`zellij kill-session agent-<task.id>`), so a same-named retry can't collide
  with the orphan.
- **Backoff:** exponential `60s × 2^(retries-1)`, capped at 15m; default **3** retries.
- **Manual retry:** **resets the retry budget** (`retries → 0`) and runs immediately,
  ignoring backoff.

## Data model (`forge/models.py`, `Task`)

| Field            | Type                 | Notes                                                        |
| ---------------- | -------------------- | ------------------------------------------------------------ |
| `retries`        | `int` (exists)       | Attempts already made. Start reading/writing it.             |
| `max_retries`    | `int = 3`            | Per-task cap; overridable at dispatch.                       |
| `available_at`   | `datetime \| None`   | Backoff gate. Task is dequeued only once this time passes.   |
| `failure_kind`   | `str \| None`        | `transient` \| `timeout` \| `declined` \| `verification` \| `terminal`. Drives retry decision; visible in UI. |

Stored in the `tasks` row (`to_row`/`from_row`); requires a SQLite migration adding
`max_retries`, `available_at`, `failure_kind` columns (existing rows default sensibly:
`max_retries=3`, `available_at=NULL`, `failure_kind=NULL`).

`list_pending` SQL becomes:

```sql
SELECT * FROM tasks
WHERE status = 'queued' AND (available_at IS NULL OR available_at <= ?)
ORDER BY created_at ASC
LIMIT ?
```

## Failure classification

`TaskStore.mark_failed` gains a `kind: str` parameter and persists it to `failure_kind`
(alongside the existing `handler_data["error"]`). The coordinator labels each failure
path in `process_pending`:

| Failure path                       | `failure_kind`  | Retryable |
| ---------------------------------- | --------------- | --------- |
| triage gate returns `False`        | `declined`      | no        |
| verify gate returns `False`        | `verification`  | no        |
| `TimeoutError` raised              | `timeout`       | **yes**   |
| any other `Exception`              | `transient`     | **yes**   |
| retry budget exhausted             | (kind retained) | no        |

## Auto-retry with backoff

On a **retryable** failure the coordinator:

1. If `task.retries < task.max_retries`: increment `retries`, set
   `available_at = now + backoff(retries)`, transition `FAILED → QUEUED`.
2. Else: leave the task `FAILED` with its `failure_kind` recorded.

`backoff(n)` = `min(FORGE_RETRY_BASE_SECONDS × 2^(n-1), FORGE_RETRY_MAX_SECONDS)`.

**Config** (`forge/config.py`, `FORGE_` prefix):

| Setting                     | Default |
| --------------------------- | ------- |
| `FORGE_MAX_RETRIES`            | `3`     |
| `FORGE_RETRY_BASE_SECONDS`     | `60`    |
| `FORGE_RETRY_MAX_SECONDS`      | `900`   |
| `FORGE_DEFAULT_TIMEOUT_SECONDS`| `1800`  |

## Execution timeouts (in-process — primary mechanism)

Each agent declares `timeout_seconds` (e.g. Echo `60`, Code `3600`). A task may override
via `handler_data["timeout_seconds"]`. The coordinator wraps each **producing** stage
call (`execute`, and `deliver` if present) in `asyncio.wait_for(..., timeout)`. On expiry
the coroutine is cancelled — freeing the concurrency slot — and a `TimeoutError`
propagates into the classification path (`timeout`, retryable).

Resolution order for the effective timeout: `handler_data["timeout_seconds"]` →
`agent.timeout_seconds` → `FORGE_DEFAULT_TIMEOUT_SECONDS` (global fallback for any agent
that doesn't declare one).

## Reaper (backstop — for restarts)

Generalize `reset_active_tasks` into a **reaper** invoked on startup **and** each
coordinator tick. It finds tasks in an active state (`triaging`/`executing`/
`verifying`/`delivering`) whose `now - updated_at` exceeds the effective timeout
(`updated_at` marks stage entry) and routes them through the **same** path as an
in-process timeout: classify as `timeout`, tear down any Zellij session, then
retry-or-fail per the budget. This replaces today's blind, budget-ignoring requeue and
catches tasks orphaned by a coordinator crash that `asyncio.wait_for` cannot see.

## Session teardown (`forge/zellij/runner.py`)

Add `ZellijRunner.kill_session(name: str)` running `zellij kill-session <name>`, tolerant
of an already-gone session (non-zero exit / "session not found" is not an error). Before
any retry or reap of a **Code** task, the coordinator calls
`kill_session(f"agent-{task.id}")`. No-op for agents that don't use Zellij.

## Manual requeue (`forge/api/tasks.py`)

New endpoint `POST /tasks/{id}/retry`:

- Allowed only when the task is `FAILED` (else `409`).
- Resets `retries → 0`, clears `available_at` (runs immediately, ignoring backoff),
  clears `failure_kind`.
- Kills any lingering `agent-<task.id>` session.
- Transitions `FAILED → QUEUED`.

(UI surfaces this as a "Retry" button in a later, separate change.)

## Out of scope

- Priority queue, task dependencies/chaining, per-repo concurrency (other themes).
- Cancelling a **healthy** running task (the Control theme — distinct from reaping a hung
  one).
- Progress heartbeats / streaming status (the Observability theme).
- Hardening the vendored `scripts/syncshot.py`.

## Testing

pytest + in-memory SQLite, existing `db`/`store`/`registry` fixtures; no real Zellij (the
runner already falls back to a direct subprocess in tests).

- `backoff(n)` produces the expected capped exponential sequence.
- Classification: triage-decline → `declined` (no requeue); verify-fail → `verification`
  (no requeue); raised `TimeoutError` → `timeout` (requeued with `available_at` set);
  generic exception → `transient` (requeued).
- `list_pending` excludes rows whose `available_at` is in the future and includes them
  once it passes.
- Retry budget: a task requeues up to `max_retries`, then stays `FAILED`.
- Reaper: an active task past its timeout is requeued (budget available) or failed
  (exhausted), and `kill_session` is invoked for Code tasks.
- In-process timeout: a slow `execute()` is cancelled at `timeout_seconds` and classified
  `timeout`.
- `POST /tasks/{id}/retry`: resets `retries`, clears the gate, requeues; rejects
  non-`FAILED` tasks with `409`.

## Success criteria

- A transient `execute()` exception is retried up to `max_retries` with backoff, then
  fails terminally with `failure_kind=transient`.
- A hung task is cancelled at its timeout, its Zellij session is killed, and the slot is
  freed — both while the coordinator runs (in-process) and after a restart (reaper).
- Triage-declines and verification-failures never auto-retry.
- `POST /tasks/{id}/retry` puts a failed task back in the queue with a fresh budget and no
  session collision.
