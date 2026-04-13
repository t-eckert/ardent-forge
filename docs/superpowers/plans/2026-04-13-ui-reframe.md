# UI Reframe — Tasks spine · Orchestrator · Memory

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development`. Steps use `- [ ]` syntax.

**Executes against:**
- `docs/superpowers/specs/2026-04-13-forge-orchestrator.md`
- `docs/superpowers/plans/2026-04-13-ui-implementation.md` (prior plan — this supersedes its Agents surface)

**Goal.** Replace the Agents spine with a Tasks spine; demote Agents + Connectors + Memory to Library facets; rename personal to-dos to Todos; add the three assistant-message variants (widget / task-dispatched / task-resolved / memory-saved-chip); wire everything to the real API endpoints from the backend refactor.

**Precondition.** Parts of this plan can ship against mocks first (naming rename, spine swap, new components with factory-driven stories). API wiring (Phase M) requires Phase F of the backend refactor to complete.

---

## Phase H — Vocabulary rename

Non-structural cleanup so subsequent phases land in a consistent naming space.

- [ ] Rename user-facing "tasks" that are really personal to-dos to **Todos** throughout the UI.
  - [ ] `schemas/task.ts` — split into `schemas/todo.ts` (personal to-dos: `manual`, `ritual`, `errand`, etc.) and `schemas/task.ts` (backend task units of work). Keep Todo's existing shape as the personal-checklist model.
  - [ ] `mocks/todo.ts` (renamed from `mocks/task.ts`) + new `mocks/task.ts` for backend tasks.
  - [ ] `today/components/focus-block.svelte` — "TASKS · DUE TODAY" → "TODOS · DUE TODAY".
  - [ ] Palette result class `task` → `todo` everywhere in `palette/types.ts` + mock data + ranking.
  - [ ] `TodayView` hero stat label "TASKS DUE" → "TODOS DUE".
- [ ] Introduce `Task` as the backend task type (status · stages · origin thread · agent · artifact).
- [ ] Update all existing copy/labels using "tasks" ambiguously.

**Exit criteria:** `grep -ri task ui/src/lib | grep -v schemas/task` returns only references to the new backend-task concept.

---

## Phase I — Tasks spine (replaces Agents spine)

Swap the sidebar fourth slot from Agents → Tasks. Agents demotes to Library.

- [ ] `chrome/components/sidebar.svelte` — change fourth spine item to **Tasks**, icon `ListChecks` (Phosphor), default weight regular, ember when active.
- [ ] `chrome/state/chrome.state.svelte.ts` — `Spine` type becomes `'today' | 'threads' | 'library' | 'tasks'`; `spineFromPath` recognises `/tasks`.
- [ ] Update all sidebar instances: Today, Threads, Library, (old Agents), Health/Workouts.
- [ ] Update `$lib/icons/index.ts` — add `ListChecks`; retain `Robot` for the agent roster page.
- [ ] New routes:
  - [ ] `routes/tasks/+page.svelte` → `TasksListView`
  - [ ] `routes/tasks/[id]/+page.svelte` → `TaskDetailView`
- [ ] Remove old Agents spine routes: `routes/agents/+page.svelte` and `routes/agents/[agent]/[run]/+page.svelte`. Their functionality migrates into Tasks detail + Library/Agents.
- [ ] Update mock palette seed to replace "agent" class with "task" class.

**Exit criteria:** sidebar shows Today · Threads · Library · Tasks; `/agents` routes return 404; palette fuzzy-find for "rename" lands on the task, not the agent run.

---

## Phase J — Tasks surface (list + detail)

New `lib/tasks/` domain. Largely rehydrates the old Agents logic but task-centric.

- [ ] `lib/tasks/` directory with standard layout (`components/`, `state/`, `_stories/`, `views/`, `index.ts`).
- [ ] `schemas/task.ts` (v2) — full shape: `id`, `title`, `kind` (`agent-run` | `manual` | `scheduled`), `agent` name, `status` (`queued`, `running`, `needs-review`, `done`, `failed`), `stages` run so far, `metas[]`, `steps[]`, `artifact?`, `originThreadId?`, `referencedByThreadIds[]`.
- [ ] `mocks/task.ts` — factories including `makeCodeTask()` (the rename), `makeTriageTask()`, `makeScheduledBriefingTask()`, etc. All schema-validated.
- [ ] Components:
  - `task-row.svelte` — kind chip + agent avatar + status chip + summary + relative time, active state w/ ember rule.
  - `task-list.svelte` — 320px panel with filter tabs (`all`, `active`, `needs-me`, `scheduled`, `failed`) and `+ new task` button.
  - `task-header.svelte` — title + queued-by + origin thread breadcrumb if present (links back).
  - `task-meta-strip.svelte` — status/duration/tokens/cost/tool-calls/tests (reuses the old run-meta-strip pattern).
  - `task-timeline.svelte` + `task-step.svelte` — stage-by-stage list with state markers.
  - `task-artifact.svelte` — eyebrow + `<WidgetHost payload={artifact} />`.
  - `task-thread-link.svelte` — "opened in" / "referenced in" chips linking to threads.
- [ ] Views:
  - `tasks-list-view.svelte` — sidebar list + empty "pick a task" state.
  - `task-detail-view.svelte` — list + header + meta strip + timeline + artifact + thread links.
- [ ] Story: `Tasks/Task detail · code-agent rename` (fullscreen).
- [ ] Route wiring per Phase I.

**Exit criteria:** `/tasks/[id]` on the rename task matches the visual of the old Agents run detail, with additional "opened in [thread]" breadcrumb.

---

## Phase K — Library facets (Agents · Connectors · Memory)

Agents and Connectors lose their spine slot; Memory is brand new. All three live under Library.

- [ ] `library/views/library-index.svelte` — add Agents, Connectors, Memory as facets alongside Fields / Daily log / Todos / Schedule / People / Wiki / Collections.
- [ ] `routes/library/agents/+page.svelte` — `AgentsRoster` (doc-style: name, icon, task_type, stages pill list, connectors, recent 3 runs linking to `/tasks/[id]`).
- [ ] `routes/library/connectors/+page.svelte` — `ConnectorsRoster` (name, badge, status (● live / ● synced / ✗ failed), last heartbeat, "re-auth" action when applicable).
- [ ] `routes/library/memory/+page.svelte` — `MemoryLibrary`:
  - Groups by type (user, feedback, project, reference).
  - Row = `name`, `description`, last-modified, trash + edit actions.
  - Detail modal (or sub-route): renders the markdown body with edit affordance.
- [ ] `routes/library/memory/[name]/+page.svelte` — edit view (monospace textarea + save; `pnpm run memory:validate` still parses).
- [ ] Mocks for each facet (seed 3–5 entries per type).
- [ ] Stories: `Library/Agents roster`, `Library/Connectors roster`, `Library/Memory`.

**Exit criteria:** every old Agents-surface concept has a Library home; sidebar count "Agents · 3" replaced by a `LIBRARY · Memory · N` row; palette finds memory entries.

---

## Phase L — Assistant message variants + chat composability

Thread conversations need three assistant-message shapes + one inline chip. Builds on the existing `assistant-message.svelte`.

- [ ] Extend `schemas/thread.ts` — `AssistantMessage.variant`:
  ```ts
  variant: 'widget' | 'task-dispatched' | 'task-resolved' | 'memory-saved';
  ```
- [ ] Add the matching payload fields:
  - `widgets: WidgetPayload[]` — unchanged, used for `variant=widget`.
  - `dispatchedTask: { id, agent, stages, status }` — for `variant=task-dispatched` (live-updating card).
  - `resolvedTask: { id, artifact, summary }` — for `variant=task-resolved` (narration + artifact widget).
  - `savedMemory: { name, description }` — for the inline chip.
- [ ] `threads/components/task-dispatched-card.svelte` — small card with agent avatar, title, stage pills (current stage pulses), SSE live-update over `/api/tasks/{id}/stream`.
- [ ] `threads/components/task-resolved-message.svelte` — wraps `assistant-message` pattern with narration + embedded `WidgetHost`.
- [ ] `threads/components/memory-saved-chip.svelte` — small inline pill ("saved — half marathon training"). Placed after the prose, before any widgets.
- [ ] Update `threads/components/assistant-message.svelte` to dispatch on `variant` and render the correct sub-component.
- [ ] Mock: extend `makeRenameThread()` to include three variants across its messages:
  1. user: "rename tClient…"
  2. assistant (task-dispatched): "I've queued this with code-agent…" + card
  3. assistant (task-resolved): "code-agent finished — 4 files…" + code.diff widget
  4. assistant (memory-saved): "I'll remember that you prefer package-scoped renames" + chip
- [ ] Story: `Threads/Thread view · Dispatch + resolution + memory save`.

**Exit criteria:** a thread story shows all four message shapes with consistent Forge avatar and voice.

---

## Phase M — API wiring (removes mocks from routes)

Requires backend Phases F (API) and E (memory) complete.

- [ ] `lib/api/client.ts` — typed client with zod parsing at every boundary. Every response `.parse()`s through the corresponding schema; failures throw loud errors in dev, reported with surface + endpoint.
- [ ] SvelteKit loaders (`+page.ts`) for each route fetch real data; components stay mock-seeded in stories.
- [ ] Hybrid mode: `VITE_API_URL` env var read at build; fallback to `/api` (same-origin) in production.
- [ ] `SSE` consumer helper for task live updates.
- [ ] `lib/stores/sync.state.svelte.ts` — read from `/api/connectors/health` periodically; drive the sidebar sync pip.
- [ ] Delete mock-only seed data from routes; stories retain mocks.

**Exit criteria:** running `pnpm dev` with `VITE_API_URL=https://ardent-forge.<tailnet>.ts.net` hits the real box; Storybook still works offline with mocks.

---

## Phase N — Polish (carried from the original plan)

Retained from `2026-04-13-ui-implementation.md` Phase 10 — dark mode, a11y, visual regression, E2E — but pushed to after the reframe lands.

- [ ] Dark mode token set + manual toggle.
- [ ] A11y audit: palette kbd, focus traps, semantic headings, aria on composer.
- [ ] Visual regression: Chromatic or Playwright snapshots on Storybook.
- [ ] E2E on the box via CI: palette navigation, thread composer round-trip, task dispatch + resolution end-to-end, memory write → next-conversation recall.

---

## Ordering

```
H (rename)          — independent, ships first
I (spine swap)      — after H
J (Tasks surface)   — after I, uses mocks
K (Library facets)  — parallel with J, uses mocks
L (message variants) — parallel with J/K, uses mocks
M (API wiring)      — after backend Phase F complete
N (polish)          — last
```

H + I + J + K + L can ship against the existing mock layer before the backend refactor is done — keeps the visual work unblocked. M is the integration point; N closes out.

---

## Out of scope

- Real-time typing indicators / streaming chat tokens — future enhancement once basic API is wired.
- Todo → Task promotion ("turn this to-do into an agent task") — natural next iteration; not part of this reframe.
- Mobile / small-viewport layouts.
- Per-thread connector scoping.
