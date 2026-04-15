---
status: ready-to-plan
title: Chat-side dispatch wiring (Phase P₂)
---

# Chat-side dispatch wiring — design spec

**Date:** 2026-04-14
**Depends on:** `2026-04-13-forge-orchestrator.md` (orchestrator turn types),
`2026-04-12-connectors-and-flexible-agents.md` (connectors + agents split).
**Supersedes a gap in:** `forge/api/chat.py` (singleton chat log, no dispatch branch).

## Context

The orchestrator spec describes three turn shapes (synchronous tool, task-dispatch, task-resolution). Today only the synchronous tool turn is actually wired through `forge/api/chat.py`. The other two are backed by working primitives (`ThreadStore`, `post_resolution`, the coordinator's resolution post-back, the Task model's `origin_thread_id`) — but the chat endpoint never writes into them.

Concrete gaps:

1. **No thread scoping.** `chat.py` uses `store.save_chat_message` / `store.list_chat_messages`, which is a singleton log per forge instance. Threads exist in `ThreadStore` but nothing in the chat path reads or writes them.
2. **No dispatch branch.** Every tool use is executed inline via `tool.execute`. There is no check of `orchestrator.resolve_tool_call`'s returned `TurnShape`, so `TASK_DISPATCH` is unreachable.
3. **No classification signal.** Even if the branch existed, no Tool or Agent today actually declares itself as dispatch-shaped, so `decide_turn_shape` has nothing to route on.

The integration test in `tests/test_orchestrator_resolution.py` and the additional guarantees in `tests/test_dispatch_loop.py` (Phase P₁) prove the *back half* of the loop works: once a Task exists with an `origin` thread link, the coordinator processes it and the orchestrator narrates the resolution back into the thread. This spec closes the *front half*.

## Goals

- Chat turns from a thread persist into that thread, not the singleton log.
- Tool uses that represent asynchronous work create real Tasks linked to the thread and return quickly, rather than blocking the chat stream.
- One classification signal, documented once, that both connector tools and agents agree on.
- The UI's existing `task-dispatched` and `task-resolved` message variants (`ui/src/lib/threads/components/`) are populated with real data.
- The manual walkthrough in `docs/runbooks/dispatch-loop.md` passes end-to-end.

## Non-goals

- Multi-user / auth on threads. One user, one box.
- Streaming task progress back into the thread mid-run. Dispatch returns "queued"; resolution returns the artifact. No live stage-by-stage narration in the thread for now.
- Migrating the existing singleton chat log to threads. Keep it available for quick ad-hoc turns; the Today composer can continue to use it.
- Retries, cancellation, or "I changed my mind" semantics on dispatched tasks. Cron/watcher tasks already exist for later; this spec covers user-initiated dispatch only.

## Design decision — where does dispatch-shape live?

The load-bearing design decision. Two candidates:

### Option A — Tool-level flag (`long_running: bool`)

`Tool` already carries `long_running`. Treat `long_running=True` as "this tool call becomes a Task rather than executing inline."

**Pros:**
- Single source of truth, already wired through the UI (`/api/connectors` exposes `long_running`).
- Works uniformly for connector tools — no agent involved.

**Cons:**
- Conflates two different things. A connector tool that takes 30s of I/O (e.g. a large scrape) is "long-running" in a different sense than "spawns an async Task with multi-stage agent processing."
- A single agent might be invoked through different tool surfaces with different needs.

### Option B — Agent-driven (dispatch by task type)

Connector tools are always inline. Dispatch happens when Forge calls a special meta-tool `dispatch_task(task_type=..., title=..., description=...)`. The orchestrator exposes this as a tool; Forge chooses it when it wants to queue work.

**Pros:**
- Clean role split: connectors never dispatch, agents only receive dispatch.
- The prompt can teach Forge *when* to dispatch by listing registered task types in the system prompt (already partly done — we list `agents=[a.task_type for a in self.agents.list()]`).
- Matches the user mental model: "Forge is dispatching a research task" rather than "Forge called a long-running tool."

**Cons:**
- Adds a synthetic tool. More surface to prompt around.
- Two tool-use styles in the same turn — inline connector tools + dispatch meta-tool — and the UI needs to distinguish them.

### Recommendation: **Option B.**

The role split in the orchestrator spec is explicit: connectors emit tool results, agents produce artifacts via dispatched tasks. Option B preserves that cleanly. `long_running` stays as a UI hint (so we can show a spinner on a slow connector tool) but does not gate task dispatch.

## Data flow

```
POST /api/chat { content, thread_id? }
  │
  ├─ if no thread_id: singleton-log path (today's behaviour)
  │
  ├─ if thread_id:
  │   ├─ thread_store.append_message(role='user', content)
  │   ├─ Build ThreadContext from recent messages
  │   ├─ orchestrator.system_prompt(thread_context=ctx)
  │   ├─ tool_schemas = orchestrator.tool_schemas() + [dispatch_task_schema]
  │   └─ stream Claude …
  │        for each tool_use block:
  │          ├─ if name == 'dispatch_task':
  │          │    ├─ Task.new(task_type, title, description, source=CHAT)
  │          │    ├─ store.save(task)
  │          │    ├─ thread_store.link_task(origin)
  │          │    ├─ thread_store.append_message(variant='task-dispatched', task_id)
  │          │    └─ return {"status": "queued", "task_id": ...} as tool_result
  │          └─ else:
  │               (existing synchronous connector tool path)
  │
  └─ final assistant prose → thread_store.append_message(role='assistant', variant='text')
```

The coordinator and `orchestrator.post_resolution` need no changes. Once the Task exists with its `origin` link, the back half of the loop (already tested) runs on its own.

## API surface changes

### `POST /api/chat`

```json
{ "content": "kick off research on Svelte 5 changes", "thread_id": "abc123" }
```

`thread_id` is optional. Omitted → current singleton-log behaviour. Present → thread-scoped behaviour described above.

### New `GET /api/chat/messages?thread_id=abc123` (optional, follow-up)

If the UI composer in `/threads/[id]` wants to render the stream result, it can keep reading `/api/threads/abc123` (already wired). This endpoint is only a nice-to-have for symmetry; not required for the dispatch loop.

### Tool schema `dispatch_task`

Synthetic tool injected by the orchestrator alongside connector tools:

```json
{
  "name": "dispatch_task",
  "description": "Queue an asynchronous task for an agent. Use when the work is too big, too slow, or too multi-step to do inline — research, code changes, planning.",
  "input_schema": {
    "type": "object",
    "properties": {
      "task_type": {"type": "string", "enum": ["<dynamically: registered task types>"]},
      "title":     {"type": "string"},
      "description": {"type": "string"}
    },
    "required": ["task_type", "title", "description"]
  }
}
```

The `enum` is populated at system-prompt build time from `self.agents.list()` task types.

## Failure cases

- **Thread doesn't exist.** `POST /api/chat` with a `thread_id` that doesn't exist → 404. Don't auto-create.
- **Dispatch with unknown task_type.** Claude occasionally hallucinates. The tool call handler validates against `agents.get(task_type)` and returns a `tool_result` with `is_error=true` and a helpful message, letting Claude retry in the same turn.
- **Dispatch succeeds but coordinator is down.** The Task sits in `queued`; the `task-dispatched` message stays in its pending state; the user refreshes and sees nothing has moved. Acceptable — the coordinator restarting will pick it up. Consider a stale-threshold warning later, not in this spec.
- **Coordinator completes but `post_resolution` fails.** Already logged in `coordinator.py` with `logger.exception`. The Task is `completed`; the thread shows the stale `task-dispatched` card forever. Mitigation is out of scope; flag for a future "reconciliation" agent.

## Tests

Alongside the implementation:

1. `tests/test_chat_thread_scoping.py`
   - synchronous tool in a thread → user + assistant messages persisted to `ThreadStore`, not to the singleton log.
   - threadless chat → goes through the singleton log (current behaviour preserved).
2. `tests/test_chat_dispatch.py`
   - dispatch tool call → Task row created with correct `origin_thread_id`, `task-dispatched` message appended.
   - unknown `task_type` → `tool_result` with `is_error=true`, no Task created.
   - full loop (already covered by `test_orchestrator_resolution.py`) — dispatched Task completes, resolution lands.
3. `docs/runbooks/dispatch-loop.md` — the manual walkthrough now passes.

## Migration / compatibility

- Existing `/api/chat` callers (UI's Today composer) keep working — they just omit `thread_id`.
- `GET /api/chat/messages` continues to return the singleton log.
- No database migration. `thread_tasks` already exists (Phase F); Task model already has the linkage via `thread_store.origin_thread_for`.
- UI: `/threads/[id]` composer needs to send `thread_id` in its POST. Small change in `ui/src/lib/threads/components/thread-composer.svelte`.

## Rollout

1. Implement in three commits:
   - (a) `chat.py` takes optional `thread_id` and persists to `ThreadStore` when provided. Synchronous tool path only.
   - (b) Add `dispatch_task` meta-tool to `orchestrator.tool_schemas()` and the dispatch branch in `chat.py`'s tool loop.
   - (c) Wire the UI composer to send `thread_id` from `/threads/[id]`.
2. Walk the runbook on the box after (c).
3. Update `MEMORY.md` project-progress entry to reflect "dispatch loop closed end-to-end."

## Open questions for review

1. Should the `task-dispatched` message include the tool_use_id from Claude, so we can correlate the eventual tool_result back to it if we ever replay the turn? Low-priority but cheap to include.
2. Do we want to cap dispatches per turn (e.g. one task per user message) to keep the conversation legible, or allow fan-out? Default to uncapped; add a limit only if it becomes a problem.
3. Is the synthetic `dispatch_task` tool discoverable enough in the prompt, or should we nudge Forge with a few-shot example in the persona? Tune after observing real usage.
