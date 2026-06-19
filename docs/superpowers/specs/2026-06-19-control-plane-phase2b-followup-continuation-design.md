---
title: Control Plane Phase 2b — Follow-up Continuation
date: 2026-06-19
status: approved
supersedes: none
parent_spec: docs/superpowers/specs/2026-06-18-dispatch-steer-control-plane-design.md
---

# Phase 2b — Follow-up Continuation

## Context

Phase 2a landed the steering states and gates: `cancelled` + `awaiting_approval`,
`Task.require_approval`, the coordinator approval gate (`resume_approved_deliveries`),
and the `cancel`/`approve`/`reject` endpoints. Phase 2b adds the remaining steer
action from the dispatch-and-steer design: **mid-flight follow-up as a queued
continuation run**.

A follow-up lets the operator say, after looking at a finished Code task, "good,
but also do X" — and have a fresh agent run **continue** from where the parent
left off: the same git worktree *and* Claude's per-directory conversation
transcript (`claude --continue`), rather than starting cold.

## The open risk this spec resolves

The parent design flagged it: a follow-up reuses the parent's worktree, but
`deliver()` in `forge/agents/code.py` currently calls `cleanup_worktree`
(`git worktree remove --force`) the moment a task opens its PR. So by the time
you would follow up on a completed task, the worktree — and the basis for
`--continue` — is gone.

**Resolution (chosen): keep worktrees after delivery; reclaim them with an
age-based reaper.** `deliver()` stops removing the worktree. A reaper becomes the
single, uniform reclaim path for *all* worktrees (completed, failed, cancelled,
rejected — none of which were ever cleaned up except completed-via-deliver before
this change). This makes follow-up uniformly possible on any recent task within
the retention window, with the only failure mode being disk usage — acceptable on
a nukable single box.

## Scope

In scope:
- `continues_task_id` on the task model + migration.
- `deliver()` no longer cleans up the worktree.
- A worktree reaper (age + reference-aware), run on the coordinator tick.
- Follow-up execution in the Code agent (reuse parent worktree, `--continue`).
- `ZellijRunner.run(continue_session=...)`.
- PR-aware (idempotent) delivery.
- `POST /api/tasks/{id}/follow-up`.

Out of scope (later phases):
- Frontend steer controls (Phase 2c).
- In-UI live streaming / web terminal.
- Dev-machine enrichment (Phase 3).

## Architecture

### 1. Data model

Add to `Task` (`forge/models.py`):

- `continues_task_id: str | None = None`

Stored as an explicit DB **column** (matching the `require_approval` precedent
from 2a), with a migration in `forge/db.py`:
`ALTER TABLE tasks ADD COLUMN continues_task_id TEXT`. `to_row` writes it;
`from_row` reads it (default `None`). `Task.new(...)` gains a `continues_task_id`
parameter.

### 2. Worktree lifecycle

- **`deliver()` change** (`forge/agents/code.py`): remove the
  `cleanup_worktree` call. The worktree (and its `worktree_path` in
  `handler_data`) persists after delivery.

- **Reaper** (new): worktrees are reclaimed by *task reference*, not by scanning
  directories. Group all tasks by their `handler_data["worktree_path"]`. A
  worktree is reclaimable when **both**:
  1. no task referencing that path is *active* — where active means status in
     `{queued, triaging, executing, verifying, delivering, awaiting_approval}`, and
  2. the newest `updated_at` across the group is older than the TTL
     (default **48h**, `FORGE_WORKTREE_TTL_HOURS`).

  Reclaim runs `git worktree remove --force <path>` then `git worktree prune`.
  Grouping by path is what keeps a *shared* worktree alive while any parent or
  recent follow-up still references it.

- **Coordinator integration**: a `reap_old_worktrees()` method on the
  coordinator, called from `tick()` alongside `reap_stuck_tasks()`. It enumerates
  candidate worktree paths from the store (tasks whose `handler_data` carries a
  `worktree_path`) and applies the rule above via the git helper.

### 3. Follow-up validity

`POST /api/tasks/{id}/follow-up` is valid only when the parent task:

- is a **Code** task that has a `worktree_path` in `handler_data` which **still
  exists on disk** — otherwise `409` ("worktree no longer available; it was
  reaped"); and
- is **not active** — status must be in `{completed, failed, awaiting_approval}`.
  A `queued`/`triaging`/`executing`/`verifying`/`delivering` parent returns `409`
  (cannot run two Claude sessions in one worktree).

Missing parent → `404`. Non-Code parent or no `worktree_path` → `409`.

**Chaining** (follow-up of a follow-up) is supported: a child resolves the
worktree from its *immediate* parent's `handler_data`; all links in the chain
point at the same shared worktree path.

### 4. Follow-up execution path

`forge/agents/code.py::execute`:

- If `task.continues_task_id` is set: load the parent, reuse its
  `worktree_path` / `repo_path` / `branch_name` (skip `ensure_repo` and
  `create_worktree`), and run the prompt with `continue_session=True`.
- Carry `worktree_path` / `repo_path` / `branch_name` forward into the
  follow-up's own `handler_data` (and result) so verify/deliver and any further
  follow-up resolve correctly.
- The session name remains per-task (`agent-<task.id>`), persisted before the run
  as today so timeout/reap can tear it down.

The follow-up's prompt is the new task's description; build the Claude prompt from
it (a continuation prompt — the conversation already holds the prior context, so
the prompt need not restate the original task).

### 5. ZellijRunner change

`ZellijRunner.run(...)` gains `continue_session: bool = False`. When true, the
generated runner invokes
`claude --print --dangerously-skip-permissions --model <m> --continue -p <prompt>`
(adds `--continue`) so the follow-up inherits the prior conversation in that
working directory. Output/exit capture, session naming, and the direct-subprocess
fallback are unchanged.

### 6. Delivery idempotency (PR-aware)

`deliver()` (and the `GitHelper`) become idempotent on the branch:

- Before creating a PR, check whether one already exists for the head branch
  (`gh pr list --head <branch> --json url` or `gh pr view <branch> --json url`).
- If a PR exists: `git push` (which updates it) and reuse the existing URL — do
  **not** call `gh pr create` (it would error "already exists").
- If none exists: `git push` + `gh pr create` as today.

This yields one evolving PR per line of work (parent + all follow-ups) and, as a
bonus, makes `deliver` safe to re-run on retries.

### 7. Steering API

`POST /api/tasks/{id}/follow-up` `{ "prompt": str }`:

- Validate per §3.
- Create a new `code` task: `continues_task_id = {id}`, same `repo`,
  `source = TaskSource.MANUAL`, `queued`, inheriting the parent's
  `require_approval`. Title/description seeded from `prompt`.
- Nudge the coordinator.
- Return the new task dict (same shape as other task endpoints).

The 2a endpoints (`cancel`/`approve`/`reject`) are unchanged. Note that with the
worktree lifecycle change, cancel/reject still only kill the Zellij session; the
abandoned worktree is reclaimed by the reaper like any other.

## Error handling

- Follow-up on a reaped/missing worktree → `409`, no task created.
- Follow-up while parent active → `409`.
- A follow-up that fails during execute follows the normal coordinator
  retry/timeout classification (Phase 2a path); its worktree is shared, so the
  reaper will not reclaim it while the follow-up or parent is active or recent.
- PR-existence check failure (e.g. `gh` error) degrades gracefully: log and fall
  back to attempting `gh pr create`, surfacing the error in the result as today.
- Reaper `git worktree remove` failure → log a warning and continue (best-effort,
  mirrors the existing `cleanup_worktree` warning).

## Testing

- **Model/DB**: `continues_task_id` roundtrip through `to_row`/`from_row`;
  migration adds the column on an existing DB.
- **Reaper**:
  - keeps a worktree when a referencing task is active;
  - keeps a worktree when the newest reference is younger than the TTL;
  - reclaims a worktree when all references are terminal and the newest is past
    the TTL;
  - shared-worktree grouping: parent terminal + recent follow-up keeps it alive.
- **Code agent follow-up**: with `continues_task_id` set, reuses the parent's
  `worktree_path` (no `create_worktree`) and calls the runner with
  `continue_session=True`; missing/reaped parent worktree is surfaced.
- **ZellijRunner**: `--continue` present iff `continue_session=True`.
- **Deliver idempotency**: existing-PR branch → push + reuse URL, no second
  `gh pr create`; fresh branch → create as before.
- **API**: valid follow-up creates a linked `code` task (correct
  `continues_task_id`, repo, inherited `require_approval`) and nudges; invalid
  parent states and reaped worktree → `409`; missing parent → `404`.

## Defaulted knobs

- Worktree TTL: **48h** (`FORGE_WORKTREE_TTL_HOURS`).
- Follow-up inherits the parent's `require_approval`.
- `continues_task_id` stored as a column (not `handler_data`).
