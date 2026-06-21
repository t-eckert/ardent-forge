---
title: Control Plane Phase 2c — Frontend Steer Controls
date: 2026-06-20
status: approved
parent_spec: docs/superpowers/specs/2026-06-18-dispatch-steer-control-plane-design.md
---

# Phase 2c — Frontend Steer Controls

## Context

Phases 2a and 2b built the backend steering surface: states (`awaiting_approval`,
`cancelled`), `require_approval` + `continues_task_id`, and the endpoints
`POST /api/tasks/{id}/{cancel,approve,reject,retry,follow-up}`. The Code agent's
result also carries an `attach_cmd` (`ssh box -t zellij attach <session>`) for
live observation. Phase 2c surfaces all of this in the task detail view so the
operator can actually steer a run from the UI — the last piece of the
dispatch-and-steer control plane.

## Scope

In scope (all in `ui/`):
- Update the stale `Task` zod schema so gated/cancelled tasks parse.
- Add typed API client mutations for the five steer endpoints.
- A status-aware `TaskSteerControls` component in the task detail view.
- Lightweight status polling while the open task is active.

Out of scope:
- In-UI log streaming (watching a run live stays the Zellij attach path — the
  one-shot runner only writes output on completion).
- Steer controls anywhere other than the task detail view (no row-level actions
  in the list; that can come later if wanted).
- Removing the dead `origin_thread_id` / `referenced_by_thread_ids` schema fields
  (chat-era leftovers; they are optional and harmless — leave them).

## Architecture

### 1. Schema update (prerequisite)

`ui/src/lib/schemas/task.ts` is out of date with the backend and would throw at
the zod parse boundary when the detail view loads a gated or cancelled task.

- `TaskStatus` enum: add `'awaiting_approval'` and `'cancelled'`.
- `Task` object: add `require_approval: z.boolean().default(false)` and
  `continues_task_id: z.string().nullable().optional()`.

This must land first; every other piece depends on the view being able to parse
these tasks.

### 2. API client mutations

Extend `api.tasks` in `ui/src/lib/api/typed.ts`. Each POSTs to an existing
endpoint and parses the returned task through the `Task` schema (the steer
endpoints all return the affected/created task):

```ts
cancel:  (id: string) => request(`/api/tasks/${id}/cancel`,  Task, { method: 'POST' }),
approve: (id: string) => request(`/api/tasks/${id}/approve`, Task, { method: 'POST' }),
reject:  (id: string) => request(`/api/tasks/${id}/reject`,  Task, { method: 'POST' }),
retry:   (id: string) => request(`/api/tasks/${id}/retry`,   Task, { method: 'POST' }),
followUp: (id: string, prompt: string) =>
  request(`/api/tasks/${id}/follow-up`, Task, {
    method: 'POST',
    body: JSON.stringify({ prompt })
  }),
```

`request` already throws `ApiError` (carrying `status` + endpoint + message) on a
non-2xx response, so callers can show a 409/400 inline.

### 3. `TaskSteerControls` component

New `ui/src/lib/tasks/components/task-steer-controls.svelte`, exported from
`ui/src/lib/tasks/index.ts`, rendered in `task-detail-view.svelte` between the
stage strip and the description block.

Props: `task: Task`.

Button set by status (a `code`-only guard applies where noted):

| Status group | Buttons |
| --- | --- |
| active: `queued` / `triaging` / `executing` / `verifying` / `delivering` | **Cancel** · *Copy attach cmd* (when `handler_data.zellij_session`) |
| `awaiting_approval` | **Approve** · **Reject** · **Follow up** (code) · *Copy attach cmd* |
| `failed` | **Retry** · **Follow up** (code) |
| `completed` | **Follow up** (code) |
| `cancelled` | — (nothing) |

Behaviour:
- **Approve / Retry**: call the matching mutation, then `invalidateAll()`.
- **Cancel / Reject** (destructive): two-step inline confirm — first click swaps
  the label to "Confirm?" (and arms a ~3s auto-disarm); second click runs the
  mutation, then `invalidateAll()`. No modal/dialog.
- **Follow up** (only rendered for `task.type === 'code'`): toggles an inline
  panel containing a `<textarea>` and Send/Cancel. Send calls
  `api.tasks.followUp(task.id, prompt)` and on success
  `goto('/tasks/' + newTask.id)`. Disabled while the prompt is empty.
- **Copy attach cmd**: shown when `handler_data.zellij_session` is present;
  copies `handler_data.attach_cmd` (falling back to
  `ssh box -t zellij attach <zellij_session>` if `attach_cmd` is absent) to the
  clipboard via `navigator.clipboard.writeText`, with a brief "Copied" state.
- **Error handling**: any mutation that throws `ApiError` is caught and rendered
  as a small inline error line beneath the buttons (e.g. follow-up on a reaped
  worktree → 409 "worktree no longer available"; approve that lost a race → 409).
  A `busy` flag disables the buttons during an in-flight request.

Buttons use the existing `Button` primitive (`$lib/components`). Destructive
actions use its destructive/ember tone if available, otherwise a muted tone with
the two-step confirm carrying the weight.

### 4. Polling

In `task-detail-view.svelte`, add a `$effect` that polls while the open task is
active:

```ts
const TERMINAL = new Set(['completed', 'failed', 'cancelled']);
$effect(() => {
  if (!active || TERMINAL.has(active.status)) return;
  const t = setInterval(() => invalidateAll(), 3000);
  return () => clearInterval(t);
});
```

Because the effect reads `active.status`, it re-subscribes when the status
changes and tears the interval down once the task reaches a terminal state.
`invalidateAll()` re-runs the page `load` (`+page.ts`), refreshing both the left
task list and the detail, so the stage strip advances and the Approve/Reject
buttons appear on their own when a gated run reaches the gate. Volume is low
(single box), so re-fetching the list every 3s is acceptable.

## Error handling

- Parse-boundary: the schema update removes the only known parse failure
  (unknown status). Any future drift still fails loudly via `ApiError` at the
  fetch boundary, as today.
- Mutation conflicts (409) and validation (400/422) surface inline in
  `TaskSteerControls`; they never crash the view.
- Clipboard: if `navigator.clipboard` is unavailable, the copy button shows a
  brief failure state rather than throwing.

## Testing

- **Schema** (`ui/src/lib/schemas/`): a vitest test that `Task` parses a task
  with `status: 'awaiting_approval'` and one with `status: 'cancelled'`, and that
  `require_approval` / `continues_task_id` round-trip.
- **API methods**: tests mirroring `ui/src/lib/api/client.test.ts` (mock
  `fetch`) asserting each new mutation hits the correct path + `POST`, and that
  `followUp` sends the `{prompt}` body.
- **TaskSteerControls** (Storybook + interaction tests, matching the existing
  `dispatch-form.stories.ts` pattern):
  - a story per status group asserting the correct buttons render (gated shows
    Approve/Reject/Follow up; failed shows Retry/Follow up; completed shows
    Follow up; cancelled shows none; non-code completed shows no Follow up);
  - an interaction test that clicking **Approve** invokes the approve method;
  - an interaction test that **Cancel** requires two clicks (first arms
    "Confirm?", second fires the mutation).

## Defaulted choices

- Poll interval: **3s**.
- Cancel/Reject: two-step inline confirm (no modal).
- Attach: copy-to-clipboard button (no in-UI terminal).
