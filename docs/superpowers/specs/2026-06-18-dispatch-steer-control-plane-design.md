---
title: Dispatch & steer control plane — remove chat, make tasks the spine
date: 2026-06-18
status: draft
area: api, ui, coordinator
---

# Dispatch & steer control plane

## Problem

The UI/API carries a conversational chat interface (in-app threads backed by an
orchestrator that talks to the Anthropic SDK). In practice the system is driven
mostly over MCP from Claude Code, which is a richer chat client than the in-app
one will ever be. Maintaining a second-best chat is real surface area — the
orchestrator's chat loop, persona/system-prompt assembly, the `ThreadStore`, the
threads UI — and every connector has to be exposed twice (to MCP and to the
orchestrator). There is no use case for conversational access away from Claude
Code (confirmed: no phone/tablet/non-dev driving).

The UI's genuine, non-redundant value is as a **control plane**: a place to
dispatch agent work, watch the task pipeline, and steer runs. This redesign
removes the chat subsystem and reorients the UI/API around **tasks** as the
primary object, with the mental model "dispatch & steer agents."

## Decisions (captured during brainstorming)

- **Center of gravity:** dispatch & steer agents. The dev environment (repos,
  dev servers) is supporting context, not the focus.
- **Execution model:** keep today's one-shot, non-interactive Claude run
  (`claude --print -p`). Do NOT move to resumable interactive sessions. "Steer"
  is delivered against the one-shot model (the "light" option).
- **Steer actions in scope:** stop/cancel, mid-flight follow-up (as a queued
  continuation run), attach & take over (one-click attach command), and
  approve/reject at gates.
- **Approval gates:** opt-in per dispatch, pausing **before deliver** (after
  verify). Default off — routine tasks run end-to-end.
- **Live observation:** UI shows pipeline status + final captured output;
  watching a run live is done by attaching to the Zellij session (the one-shot
  runner only writes output on completion, so in-UI streaming is out of scope).
- **Anthropic SDK:** keep the `anthropic` dependency in `pyproject.toml` even
  though chat is removed — it is expected to be reused by future systems. Remove
  only chat's *use* of it.

## Non-goals

- No resumable/interactive agent sessions (explicitly deferred).
- No in-UI live output streaming.
- No in-UI web terminal — "take over" is a copyable attach command.
- No Phase 3 dev-machine enrichment (dev-server controls, live dev URLs, richer
  Zellij visibility) in this spec — noted as the next chapter only.

## Architecture

### Removal (the chat subsystem comes out as a unit)

- **API:** delete `forge/api/chat.py`, `forge/api/threads.py` and their router
  registrations in `forge/main.py`.
- **Orchestrator chat machinery:** remove the chat loop in
  `forge/orchestrator/__init__.py`, plus `persona.py`, `system_prompt.py`,
  `dispatch.py`, `narration.py`, `notebook_context.py`, and `post_resolution`.
  If nothing in `forge/orchestrator/` survives, remove the package; otherwise
  keep only what non-chat code still imports (verified during implementation).
- **`forge/thread_store.py`:** remove the `ThreadStore` class and drop its
  tables from the schema/migrations.
- **Task↔thread linkage:** remove `origin_thread_id` and
  `referenced_by_thread_ids` from `forge/api/tasks.py` (request model, create
  path, and `get`/`list` enrichment).
- **Coordinator:** drop the `orchestrator` constructor parameter and the
  `post_resolution` call (coordinator.py:362). Finished tasks carry their own
  `result`; no narration is posted anywhere.
- **`forge/main.py` lifespan:** remove orchestrator construction, `thread_store`
  construction, the `chat.configure(...)` calls, and the `threads_api` /
  `chat` router includes. Leave connector/agent/coordinator wiring intact.
- **UI:** delete `ui/src/routes/threads/` and `ui/src/routes/threads/[id]/` and
  remove threads/chat from navigation.

**Explicitly untouched:** the MCP server (`forge/mcp/`, still the primary
interface), connectors (they feed agents and MCP directly), the Linear poller
and PR-on-delivery comment, schedules, memory, repos, notebook/weather read
APIs, metrics, uploads.

### Tasks as the spine — state & data model

Pipeline today:

```
queued → triaging → executing → verifying → delivering → completed
failed ───────────────────── requeue ──────────────────────┘
```

Add two states (in `forge/state.py`):

- `cancelled` — terminal. The user stopped the run.
- `awaiting_approval` — non-terminal pause inserted between `verifying` and
  `delivering` when the task opted into approval. Resolves to `delivering`
  (approve) or `cancelled` (reject).

Resulting flow:

```
queued → triaging → executing → verifying ─┬─→ delivering → completed
                                           └─→ awaiting_approval ─┬─→ delivering → completed
                                                                  └─→ cancelled
any active state ─ cancel ─→ cancelled
```

Task fields:

- `require_approval: bool` (default `false`) — set at dispatch; when true the
  coordinator pauses into `awaiting_approval` after a passing `verify`, before
  `deliver`.
- `continues_task_id: str | None` — set on a follow-up task; points at the
  parent whose worktree and Claude conversation the follow-up continues.

(Storage: prefer explicit columns if the task schema uses them; otherwise
`handler_data`. Implementation chooses to match the existing pattern in
`forge/store.py`.)

### Steering API

New endpoints under the existing `/api/tasks` router (joining
`POST /{id}/retry`):

- `POST /api/tasks/{id}/cancel` — kill the Zellij session
  (`forge/zellij/kill_session`) and set state `cancelled`. Valid from any active
  state. No-op-safe if the session is already gone.
- `POST /api/tasks/{id}/follow-up` `{ "prompt": str }` — create a new task with
  `continues_task_id = {id}`, the same `repo`, and queued state. The Code agent's
  `execute` detects `continues_task_id`, reuses the parent's worktree, and runs
  `claude --continue -p <prompt>` (see ZellijRunner change). Returns the new
  task. Only valid when the parent has a worktree (i.e. a Code task that reached
  at least `executing`).
- `POST /api/tasks/{id}/approve` — valid only in `awaiting_approval`; advances
  to `delivering`.
- `POST /api/tasks/{id}/reject` — valid only in `awaiting_approval`; sets
  `cancelled` (and tears down the worktree/session as the cancel path does).

`GET /api/tasks/{id}` already returns status, `result`, `zellij_session`, and
`attach_cmd`; the UI surfaces these. Invalid-state transitions return HTTP 409.

### Coordinator changes

- **Approval pause:** after `verify` returns truthy, if `require_approval` is
  set, transition the task to `awaiting_approval` and stop advancing it. A task
  in `awaiting_approval` is skipped by the dequeue loop until `approve`/`reject`
  flips it. `approve` re-enters the loop at `delivering`.
- **Cancellation:** `cancel` sets `cancelled` and kills the session out-of-band;
  the coordinator must treat `cancelled` as terminal and never re-advance it.
  Reuse the existing session-teardown path from the timeout/reaper work.
- **Follow-up continuation:** a task with `continues_task_id` runs the normal
  pipeline, but `execute` resolves the worktree from the parent task and passes a
  "continue" flag through to the runner instead of creating a fresh worktree.

### ZellijRunner change

`ZellijRunner.run(...)` gains a `continue_session: bool = False` parameter (name
to match house style). When true, the generated runner invokes
`claude --print --dangerously-skip-permissions --model <m> --continue -p <prompt>`
(adds `--continue`) so the follow-up inherits the prior conversation in that
working directory. All other behavior (output/exit capture, session naming,
direct-subprocess fallback) is unchanged.

### UI reorganization (task-centric)

Navigation: **Tasks** (landing) · **Repos** · **Library** · **Settings**.
`threads` removed; `today` folds into the Tasks landing.

- **Tasks (home):** a **dispatch form** (repo select, prompt textarea, agent
  select defaulting to Code, "require approval before delivering" toggle) above
  a live pipeline view — tasks grouped by state (queued / running / awaiting
  approval / done / failed-cancelled). This replaces chat's dispatch path and is
  the app's primary working surface.
- **Task detail (`tasks/[id]`):** stage timeline (triage → execute → verify →
  deliver), final output, verification result, PR link, and **steer controls**:
  - **Stop** → `POST .../cancel` (shown for active states)
  - **Follow-up** → prompt box → `POST .../follow-up` (shown once a worktree
    exists)
  - **Attach** → copies the `ssh box -t zellij attach agent-<id>` command
  - **Approve / Reject** → shown only in `awaiting_approval`
- **Library** (agents, connectors, memory, schedules, log) and **Repos** stay
  essentially as-is — supporting/config surfaces. Repos is where Phase 3
  controls would later land.

## Data flow

```
Dispatch form / MCP / Linear / cron  →  POST /api/tasks (queued)
  →  coordinator dequeue  →  triage → execute (Zellij one-shot) → verify
       →  [require_approval?] ── no ──→ deliver → completed
                             └─ yes ──→ awaiting_approval
                                          → approve → deliver → completed
                                          → reject  → cancelled
  follow-up:  POST /api/tasks/{id}/follow-up → new queued task
              (continues_task_id) → execute reuses worktree + `claude --continue`
  cancel:     POST /api/tasks/{id}/cancel → kill session → cancelled
```

## Phasing

The spec covers the whole vision; implementation ships in independently
shippable phases.

- **Phase 1 — Subtraction & dispatch.** Remove the chat subsystem, rewire the
  coordinator (drop `post_resolution`/orchestrator), strip thread linkage,
  delete the threads UI, and make Tasks the landing surface with the dispatch
  form. Result: a clean control plane that already does dispatch + monitor.
- **Phase 2 — Steering.** Add `cancelled` and `awaiting_approval` states, the
  four `/api/tasks` endpoints, the ZellijRunner `--continue` path, the
  coordinator pause/resume + cancel + follow-up logic, and the task-detail steer
  controls.
- **Phase 3 — Dev-machine enrichment (future, not specced here).** Dev-server
  start/stop, live dev URLs, richer Zellij visibility, system vitals.

The implementation plan is written for **Phase 1 first**; Phase 2 gets its own
plan after Phase 1 lands.

## Testing

- **Backend (pytest, in-memory SQLite):**
  - Phase 1: assert nothing imports the removed modules; existing task/schedule/
    memory/repo API tests still pass; coordinator runs a task end-to-end with no
    orchestrator present.
  - Phase 2: coordinator gate path (`require_approval` → `awaiting_approval` →
    approve → `delivering`; reject → `cancelled`); `cancel` sets `cancelled` and
    invokes session teardown; `follow-up` creates a task with `continues_task_id`
    and the runner receives the continue flag (ZellijRunner mocked); invalid
    transitions return 409.
- **Frontend:** Storybook/component tests for the dispatch form and the steer
  controls (including state-gated visibility of Approve/Reject/Follow-up); a
  Playwright smoke for the Tasks landing and task detail (falls back to mock
  data when the API is unreachable, per existing convention).

## Open risks

- **Orchestrator package survival:** some non-chat code may import a helper from
  `forge/orchestrator/`. Implementation verifies and keeps only what survives;
  if nothing does, the package is deleted.
- **Worktree lifetime for follow-ups:** a follow-up reuses the parent's
  worktree, so the parent's worktree must not be cleaned up until follow-ups are
  done. Phase 2 must reconcile this with `deliver`'s existing
  `cleanup_worktree`. Decision deferred to the Phase 2 plan, flagged here.
