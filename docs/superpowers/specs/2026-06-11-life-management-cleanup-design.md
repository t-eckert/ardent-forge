---
title: Life Management Cleanup
date: 2026-06-11
status: approved
---

# Life Management Cleanup

Remove vestigial code left over from when Ardent Forge was a "life management agent" (fitness tracking, personal todos, spending, field research). The project has pivoted to a developer-toolbox control plane; this sweep cuts everything that doesn't serve that purpose.

## What Stays

Weather (connector + `/api/weather` + Today dashboard card), SpeedtestConnector, NotebookConnector (read + write), all active agents (Code, Echo, Plan, Tickets), `guardrails.py`, `verify.py`, the full widget kernel for code-diff and result widgets.

## What Goes

### Backend — deletions

| Path | Reason |
|------|--------|
| `forge/workout/` | Strava client, workout notebook integration, weekly summaries |
| `forge/agents/research.py` | Never registered; references a non-existent `research_prompt` module |
| `forge/api/todos.py` | Not routed in `create_app()` |
| `forge/api/fields.py` | Not routed in `create_app()` |

### Backend — edits

- `forge/config.py` — remove `strava_client_id`, `strava_client_secret`, `strava_refresh_token`, `strava_token_path`

### Frontend — module deletions

| Path | Reason |
|------|--------|
| `ui/src/lib/fields/` | Health/fields module (workouts view, activity table, readiness cards) |
| `ui/src/lib/widgets/places-map/` | No backing API |
| `ui/src/lib/widgets/purchases/` | No backing API |
| `ui/src/lib/widgets/workouts/` | Backed by the deleted workout module |
| `ui/src/lib/today/components/yesterday-summary.svelte` | Not used in today-view |
| `ui/src/lib/today/components/overnight-digest.svelte` | Not used in today-view |
| `ui/src/lib/today/components/focus-block.svelte` | Workout/todo-centric, not used in today-view |
| `ui/src/lib/today/components/today-shape.svelte` | Not used in today-view |
| `ui/src/lib/today/components/hero-greeting.svelte` | Todo-centric, not used in today-view |
| `ui/src/lib/components/pin-marker.svelte` | Only used by places-map widget |
| `ui/src/stories/Button.svelte`, `Header.svelte`, `Page.svelte` + related `.css`/`.stories`/`.mdx` | Storybook boilerplate |
| `ui/src/lib/schemas/widgets/places-map.ts`, `purchases.ts`, `workouts.ts` | No backing widgets |
| `ui/src/lib/schemas/field.ts`, `schemas/todo.ts` | No backing API |
| `ui/src/lib/mocks/widgets/places-map.ts`, `purchases.ts`, `workouts.ts` | No backing widgets |
| `ui/src/lib/mocks/field.ts`, `mocks/todo.ts` | No backing API |
| `ui/src/lib/library/components/field-card.svelte` | Only used by fields views |
| `ui/src/lib/library/components/fields-grid.svelte` | Only used by fields views |
| `ui/src/lib/library/views/fields-index.svelte` | Fields library view |

### Frontend — scattered edits

| File | Change |
|------|--------|
| `ui/src/lib/widgets/index.ts` | Remove exports for Purchases, Workouts, PlacesMap |
| `ui/src/lib/widgets/kernel/widget-host.svelte` | Remove imports + branches for `finance.purchases`, `health.workouts`, `places.map` |
| `ui/src/lib/schemas/widgets/index.ts` | Remove imports/re-exports for purchases, workouts, places-map |
| `ui/src/lib/schemas/primitives.ts` | Remove `'strava'` from sync source enum |
| `ui/src/lib/schemas/task.ts` | Remove `'research'` from `TaskKind` enum |
| `ui/src/lib/types.ts` | Remove `"research" \| "report" \| "notebook"` from `TaskType` |
| `ui/src/lib/palette/types.ts` | Remove `'workout' \| 'todo'` from `ResultClass` |
| `ui/src/lib/palette/components/palette-overlay.svelte` | Remove workout/todo label entries and sort order |
| `ui/src/lib/palette/components/result-row.svelte` | Remove workout icon entry |
| `ui/src/lib/palette/_stories/mock-data.ts` | Remove workout/todo mock results |
| `ui/src/lib/mocks/widgets/index.ts` | Remove purchases/workouts/places-map exports |
| `ui/src/lib/mocks/agent.ts` | Remove `strava-pull` mock run |
| `ui/src/lib/mocks/task.ts` | Remove research task mock |
| `ui/src/lib/mocks/thread.ts` | Remove purchases mock thread; trim workout/purchases references from preview text |
| `ui/src/lib/mocks/widgets/result.ts` | Remove `'research output'` label |
| `ui/src/lib/tasks/components/task-row.svelte` | Remove `research` case |
| `ui/src/lib/tasks/tasks.stories.ts` | Remove research task story |
| `ui/src/lib/library/views/agents-roster.svelte` | Remove `research` entry |
| `ui/src/lib/library/views/connectors-roster.svelte` | Remove `strava` entry |
| `ui/src/lib/library/index.ts` | Remove fields-related exports |
| `ui/src/lib/stores/pinned.state.svelte.ts` | Remove health-workouts and redpanda field pins |
| `ui/src/lib/stores/sync.state.svelte.ts` | Remove strava sync entry |
| `ui/src/lib/chrome/components/breadcrumb-strip.svelte` | Remove "strava synced" from meta comment |
| `ui/src/lib/chrome/components/breadcrumb-strip.stories.ts` | Remove health/strava story entries |
| `ui/src/lib/agents/components/agent-row.svelte` | Remove `strava-pull` case |
| `ui/src/lib/api/adapters.test.ts` | Update research task fixtures to use `code` agent type |

## Execution

Single branch, one coordinated sweep. Delete files first, then edit files with remaining references. Run `uv run pytest -q` and `pnpm check` after to confirm no stray imports remain. Merge when both pass.

## Out of Scope

- SpeedtestConnector UI (tracked separately as a new feature)
- Any new functionality
