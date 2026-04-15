# Runbook — thread → task → resolution loop

The loop this runbook exercises:

```
user message in thread
  └─ Forge chat turn
       └─ task-dispatch tool call
            └─ Task row created, thread_tasks row linked (relation='origin')
                 └─ Coordinator picks up pending task
                      └─ Agent runs stages
                           └─ orchestrator.post_resolution
                                └─ thread gets 'task-resolved' message
                                     └─ UI /threads/[id] renders ResolvedTask variant
```

## Status as of Phase P₁

- **Back half of loop (coordinator → resolution posted to origin thread):** wired
  and covered by `tests/test_orchestrator_resolution.py` and
  `tests/test_dispatch_loop.py`.
- **Front half (chat turn → Task row with origin_thread_id):** NOT yet wired.
  `forge/api/chat.py` currently executes all tool calls synchronously and
  operates on the singleton chat log rather than thread-scoped conversations.
  Phase P₂ is the spec+implementation for this.

## When Phase P₂ lands — manual walkthrough

### Prerequisites

- Box is running forge.service and reachable at `ardent-forge.tail…ts.net:8000`.
- `FORGE_ANTHROPIC_API_KEY` is set (otherwise chat falls back to the configured-message path).
- At least one agent of a non-trivial type is registered (e.g. `research` or `code`).
- UI dev server is running locally with `VITE_API_PROXY` pointing at the box, or
  the built UI is served by Caddy on the box.

### 1. Create a thread from the UI

- Navigate to `/threads` and create a new thread (title: "Dispatch smoke test",
  kind: `code+tools`).
- Note the thread id from the URL (`/threads/<id>`).

### 2. Send a dispatch-shaped message

Message content that should trigger a task-dispatch tool call:

> "Kick off a research task that collects the latest Svelte 5 breaking changes."

The orchestrator should:

1. Stream a short "dispatching…" prose paragraph.
2. Emit a tool call whose resolved `TurnShape` is `TASK_DISPATCH`.
3. The chat endpoint should create a Task row via `TaskStore.save`, link it
   to the current thread with `relation='origin'`, and append a
   `task-dispatched` variant message.
4. Return to the UI quickly — do not block on coordinator completion.

### 3. Confirm via the API

```
curl -s "$BOX/api/tasks?origin_thread_id=<thread-id>" | jq
```

Expected: one Task in status `queued` (or already `executing`) with
`origin_thread_id === <thread-id>`.

```
curl -s "$BOX/api/threads/<thread-id>" | jq '.messages[-1]'
```

Expected: the most recent message has `variant: "task-dispatched"` and a
`task_id` matching the Task above.

### 4. Watch the coordinator

On the box:

```
sudo journalctl -u ardent-forge -f
```

Expected log lines:

```
coordinator: picked up task <id> (type=research)
research-agent execute stage start
research-agent execute stage complete
orchestrator.post_resolution for task <id>
```

### 5. Confirm resolution landed

```
curl -s "$BOX/api/threads/<thread-id>" | jq '.messages[-1]'
```

Expected: `variant: "task-resolved"`, `content` includes the agent name and
task title, `widgets` has one entry with the agent's aggregated result.

### 6. Confirm in UI

Refresh `/threads/<thread-id>`. Expected:

- The `task-dispatched` card is now shown in its completed state.
- A new `task-resolved` message appears, rendered by
  `ui/src/lib/threads/components/task-resolved-message.svelte`, with the
  artifact widget embedded.

### 7. Check metrics

```
curl -s "$BOX/metrics" | grep -E 'forge_(chat_turns|resolution_posts|tasks)_total'
```

Expected: `forge_chat_turns_total{shape="task_dispatch"}` incremented by 1,
`forge_resolution_posts_total{agent="research-agent"}` incremented by 1.

## Failure modes to watch for

- **Resolution lands but UI doesn't render it** — check the `variant` field
  survives `adaptMessage` in `ui/src/lib/api/adapters.ts`.
- **Task completes but no resolution posted** — confirm the task actually has
  an origin thread (`thread_store.origin_thread_for(task_id)` returns a row).
  `test_orchestrator_resolution.py::test_non_thread_task_stays_silent` pins
  the expected silent behaviour when there's no origin.
- **Double resolution** — should be impossible because `process_pending()`
  only picks up tasks with pending status. `test_dispatch_loop.py::test_reprocessing_does_not_double_post` pins this.
