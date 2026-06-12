# Life Management Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all vestigial code from Ardent Forge's life-management-agent era (Strava/workouts, personal todos, field research, purchases, places-map) in one coordinated sweep.

**Architecture:** Pure deletion + surgical edits — no new code. Delete dead modules first (backend, then frontend), then fix up scattered references in files that stay. Verify with `uv run pytest -q` and `pnpm check` at the end of each phase, then commit.

**Tech Stack:** Python 3.13 (uv/pytest), SvelteKit 2 / Svelte 5 / TypeScript (pnpm/check)

---

### Task 1: Delete dead backend modules

**Files:**
- Delete: `forge/workout/` (entire directory)
- Delete: `forge/agents/research.py`
- Delete: `forge/api/todos.py`
- Delete: `forge/api/fields.py`

- [ ] **Step 1: Delete the workout module**

```bash
rm -rf forge/workout
```

- [ ] **Step 2: Delete the research agent**

```bash
rm forge/agents/research.py
```

- [ ] **Step 3: Delete the dead API routers**

```bash
rm forge/api/todos.py forge/api/fields.py
```

- [ ] **Step 4: Verify no remaining imports reference deleted modules**

```bash
grep -rn "from forge.workout\|from forge.agents.research\|forge.api.todos\|forge.api.fields" forge/ tests/
```

Expected: no output.

---

### Task 2: Remove Strava config fields

**Files:**
- Modify: `forge/config.py`

- [ ] **Step 1: Remove the Strava config block**

In `forge/config.py`, delete lines 27–33 (the Strava comment + four fields):

```python
    # Strava — OAuth creds + rotating refresh token state.
    # REFRESH_TOKEN is seed-only: the connector persists the latest token
    # to TOKEN_PATH and uses that as the source of truth afterward.
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_refresh_token: str = ""
    strava_token_path: str = "/data/ardent-forge/strava/tokens.json"
```

After removal the `# Repos` block (previously line 35) should immediately follow the `tavily_api_key` field.

- [ ] **Step 2: Verify**

```bash
grep -n "strava" forge/config.py
```

Expected: no output.

---

### Task 3: Run backend tests and commit

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest -q
```

Expected: all tests pass (or pre-existing failures only — none introduced by this change).

- [ ] **Step 2: Commit**

```bash
git add -u forge/
git commit -m "chore: remove life-management backend (workout, research, todos, fields, strava config)"
```

---

### Task 4: Delete dead frontend modules

**Files:**
- Delete: `ui/src/lib/fields/` (entire directory)
- Delete: `ui/src/lib/widgets/places-map/` (entire directory)
- Delete: `ui/src/lib/widgets/purchases/` (entire directory)
- Delete: `ui/src/lib/widgets/workouts/` (entire directory)
- Delete: `ui/src/lib/today/components/yesterday-summary.svelte`
- Delete: `ui/src/lib/today/components/overnight-digest.svelte`
- Delete: `ui/src/lib/today/components/focus-block.svelte`
- Delete: `ui/src/lib/today/components/today-shape.svelte`
- Delete: `ui/src/lib/today/components/hero-greeting.svelte`
- Delete: `ui/src/lib/components/pin-marker.svelte`
- Delete: `ui/src/stories/Button.svelte`, `ui/src/stories/Button.stories.svelte`, `ui/src/stories/button.css`
- Delete: `ui/src/stories/Header.svelte`, `ui/src/stories/Header.stories.svelte`, `ui/src/stories/header.css`
- Delete: `ui/src/stories/Page.svelte`, `ui/src/stories/Page.stories.svelte`, `ui/src/stories/page.css`
- Delete: `ui/src/stories/Configure.mdx`
- Delete: `ui/src/lib/schemas/widgets/places-map.ts`
- Delete: `ui/src/lib/schemas/widgets/purchases.ts`
- Delete: `ui/src/lib/schemas/widgets/workouts.ts`
- Delete: `ui/src/lib/schemas/field.ts`
- Delete: `ui/src/lib/schemas/todo.ts`
- Delete: `ui/src/lib/mocks/widgets/places-map.ts`
- Delete: `ui/src/lib/mocks/widgets/purchases.ts`
- Delete: `ui/src/lib/mocks/widgets/workouts.ts`
- Delete: `ui/src/lib/mocks/field.ts`
- Delete: `ui/src/lib/mocks/todo.ts`
- Delete: `ui/src/lib/library/components/field-card.svelte`
- Delete: `ui/src/lib/library/components/fields-grid.svelte`
- Delete: `ui/src/lib/library/views/fields-index.svelte`

- [ ] **Step 1: Delete widget modules**

```bash
rm -rf ui/src/lib/fields
rm -rf ui/src/lib/widgets/places-map ui/src/lib/widgets/purchases ui/src/lib/widgets/workouts
```

- [ ] **Step 2: Delete unused today components**

```bash
rm ui/src/lib/today/components/yesterday-summary.svelte \
   ui/src/lib/today/components/overnight-digest.svelte \
   ui/src/lib/today/components/focus-block.svelte \
   ui/src/lib/today/components/today-shape.svelte \
   ui/src/lib/today/components/hero-greeting.svelte
```

- [ ] **Step 3: Delete pin-marker and Storybook boilerplate**

```bash
rm ui/src/lib/components/pin-marker.svelte
rm ui/src/stories/Button.svelte ui/src/stories/Button.stories.svelte ui/src/stories/button.css
rm ui/src/stories/Header.svelte ui/src/stories/Header.stories.svelte ui/src/stories/header.css
rm ui/src/stories/Page.svelte ui/src/stories/Page.stories.svelte ui/src/stories/page.css
rm ui/src/stories/Configure.mdx
```

- [ ] **Step 4: Delete dead schemas and mocks**

```bash
rm ui/src/lib/schemas/widgets/places-map.ts \
   ui/src/lib/schemas/widgets/purchases.ts \
   ui/src/lib/schemas/widgets/workouts.ts \
   ui/src/lib/schemas/field.ts \
   ui/src/lib/schemas/todo.ts
rm ui/src/lib/mocks/widgets/places-map.ts \
   ui/src/lib/mocks/widgets/purchases.ts \
   ui/src/lib/mocks/widgets/workouts.ts \
   ui/src/lib/mocks/field.ts \
   ui/src/lib/mocks/todo.ts
```

- [ ] **Step 5: Delete dead library components**

```bash
rm ui/src/lib/library/components/field-card.svelte \
   ui/src/lib/library/components/fields-grid.svelte \
   ui/src/lib/library/views/fields-index.svelte
```

---

### Task 5: Fix widget index and kernel

**Files:**
- Modify: `ui/src/lib/widgets/index.ts`
- Modify: `ui/src/lib/widgets/kernel/widget-host.svelte`
- Modify: `ui/src/lib/schemas/widgets/index.ts`
- Modify: `ui/src/lib/mocks/widgets/index.ts`

- [ ] **Step 1: Update `ui/src/lib/widgets/index.ts`**

Remove the three vestigial exports. Result:

```typescript
export { default as WidgetShell } from './components/widget-shell.svelte';
export { default as WidgetHost } from './kernel/widget-host.svelte';
export { default as CodeDiff } from './code-diff/code-diff.svelte';
export { default as Weather } from './weather/weather.svelte';
export { default as Result } from './result/result.svelte';
export { default as CodeResult } from './code-result/code-result.svelte';
```

- [ ] **Step 2: Update `ui/src/lib/widgets/kernel/widget-host.svelte`**

Remove the three vestigial imports and their `{:else if}` branches. Result:

```svelte
<script lang="ts">
    import type { WidgetPayload } from '$lib/schemas/widgets';
    import CodeDiff from '../code-diff/code-diff.svelte';
    import Weather from '../weather/weather.svelte';
    import Result from '../result/result.svelte';
    import CodeResult from '../code-result/code-result.svelte';

    /**
     * Renders any tool payload by discriminating on `tool`. Widget-host is the single
     * entry point the chat renderer and agent-run artifact both use — add a new case here
     * whenever a new widget ships.
     *
     * The `payload` prop is a discriminated union; the compiler enforces exhaustiveness
     * (remove a case and TS complains about the uncovered branch).
     */

    interface Props {
        payload: WidgetPayload;
    }

    let { payload }: Props = $props();
</script>

{#if payload.tool === 'code.diff'}
    <CodeDiff {payload} />
{:else if payload.tool === 'weather.forecast'}
    <Weather {payload} />
{:else if payload.tool === 'result'}
    <Result {payload} />
{:else if payload.tool === 'code.result'}
    <CodeResult {payload} />
{:else}
    <div class="font-mono text-[11px] text-[var(--color-warn)]">
        unknown tool: {(payload as { tool: string }).tool}
    </div>
{/if}
```

- [ ] **Step 3: Update `ui/src/lib/schemas/widgets/index.ts`**

Remove the three vestigial imports, re-exports, and union members. Result:

```typescript
import { z } from 'zod';
import { CodeDiffPayload } from './code-diff';
import { WeatherPayload } from './weather';
import { ResultPayload } from './result';
import { CodeResultPayload } from './code-result';

export * from './code-diff';
export * from './weather';
export * from './result';
export * from './code-result';

/**
 * Discriminated union of every widget payload the assistant can emit.
 * Add new widget schemas here so `widget-host` stays exhaustive.
 */
export const WidgetPayload = z.discriminatedUnion('tool', [
    CodeDiffPayload,
    WeatherPayload,
    ResultPayload,
    CodeResultPayload
]);
export type WidgetPayload = z.infer<typeof WidgetPayload>;
```

- [ ] **Step 4: Update `ui/src/lib/mocks/widgets/index.ts`**

Remove the three vestigial re-exports. Result:

```typescript
export * from './code-diff';
export * from './weather';
export * from './result';
export * from './code-result';
```

---

### Task 6: Fix type definitions

**Files:**
- Modify: `ui/src/lib/schemas/primitives.ts`
- Modify: `ui/src/lib/schemas/task.ts`
- Modify: `ui/src/lib/types.ts`

- [ ] **Step 1: Remove `'strava'` from `Source` enum in `ui/src/lib/schemas/primitives.ts`**

```typescript
export const Source = z.enum([
    'notebook',
    'garmin',
    'linear',
    'github',
    'calendar',
    'plaid',
    'osm',
    'uptime',
    'astro',
    'manual'
]);
```

- [ ] **Step 2: Remove `'research'` from `TaskKind` in `ui/src/lib/schemas/task.ts`**

```typescript
export const TaskKind = z.enum(['code', 'plan', 'tickets', 'echo']);
```

- [ ] **Step 3: Remove vestigial variants from `TaskType` in `ui/src/lib/types.ts`**

```typescript
export type TaskType = "code" | "triage";
```

---

### Task 7: Fix palette

**Files:**
- Modify: `ui/src/lib/palette/types.ts`
- Modify: `ui/src/lib/palette/components/palette-overlay.svelte`
- Modify: `ui/src/lib/palette/components/result-row.svelte`
- Modify: `ui/src/lib/palette/_stories/mock-data.ts`

- [ ] **Step 1: Remove `'workout'` and `'todo'` from `ResultClass` in `ui/src/lib/palette/types.ts`**

```typescript
export type ResultClass = 'note' | 'task' | 'thread' | 'action';
```

- [ ] **Step 2: Update `ui/src/lib/palette/components/palette-overlay.svelte`**

Remove `workout` and `todo` from `classLabels` and `order`:

```typescript
    const classLabels: Record<PaletteResult['class'], string> = {
        task: 'TASKS',
        note: 'NOTES',
        thread: 'THREADS',
        action: 'ACTIONS'
    };

    const order: PaletteResult['class'][] = ['task', 'thread', 'note', 'action'];
```

- [ ] **Step 3: Update `ui/src/lib/palette/components/result-row.svelte`**

Remove `workout` and `todo` from `classConfig`. Remove `Heartbeat` from the import (`Sun` is also unused — remove it too). Remove `fg` entirely — no remaining entry needs a custom foreground colour. Update the template to inline `'var(--color-paper)'`.

New `<script>` block:

```typescript
<script lang="ts">
    import { Command } from 'bits-ui';
    import type { PaletteResult } from '../types';
    import { ChatCircle, Code, ListChecks, ArrowRight } from '$lib/icons';
    import { Meta } from '$lib/typography';

    interface Props {
        result: PaletteResult;
        onselect: (r: PaletteResult) => void;
    }

    let { result, onselect }: Props = $props();

    const classConfig = {
        note: { icon: Code, bg: 'var(--color-signal)' },
        task: { icon: ListChecks, bg: 'var(--color-ink)' },
        thread: { icon: ChatCircle, bg: 'var(--color-graphite)' },
        action: { icon: ArrowRight, bg: 'var(--color-ink)' }
    } as const;

    const cfg = $derived(classConfig[result.class]);
    const Icon = $derived(cfg.icon);
</script>
```

In the template, update the icon span's style to remove the `color` reference:

```svelte
    <span
        class="flex items-center justify-center w-[22px] h-[22px] rounded-[4px] flex-shrink-0"
        style="background: {cfg.bg}; color: var(--color-paper);"
    >
```

- [ ] **Step 4: Replace `ui/src/lib/palette/_stories/mock-data.ts` with clean dev-box entries**

```typescript
import type { PaletteResult } from '../types';

/** Seed index used by the palette story and the default store until the real index lands. */
export const MOCK_RESULTS: PaletteResult[] = [
    {
        id: 'note-today-log',
        label: "Today's log",
        breadcrumb: 'Library › Notebook › Log',
        href: '/library/log/today',
        class: 'note',
        hint: '2026-04-12.md',
        pinned: true
    },
    {
        id: 'thread-morning',
        label: 'Morning briefing',
        breadcrumb: 'Threads',
        href: '/threads/morning-briefing',
        class: 'thread',
        hint: '06:12',
        recentBoost: 8
    },
    {
        id: 'task-rename',
        label: 'Rename tClient → temporalClient',
        breadcrumb: 'Tasks',
        href: '/tasks/01KP000000000000000000CODE',
        class: 'task',
        hint: 'code · executing'
    },
    {
        id: 'action-open-shell',
        label: 'Open Zellij session',
        breadcrumb: 'Action · attaches to agent session',
        class: 'action',
        keywords: ['zellij', 'session', 'attach', 'terminal']
    }
];
```

---

### Task 8: Fix mock data

**Files:**
- Modify: `ui/src/lib/mocks/agent.ts`
- Modify: `ui/src/lib/mocks/task.ts`
- Modify: `ui/src/lib/mocks/thread.ts`
- Modify: `ui/src/lib/mocks/widgets/result.ts`

- [ ] **Step 1: Remove the `strava-pull` run from `ui/src/lib/mocks/agent.ts`**

In `makeAgentRunList()`, delete the block:

```typescript
        makeAgentRun({
            id: 'run-cron-strava',
            kind: 'strava-pull',
            startedIso: hoursAgoIso(0.5),
            durationLabel: 'every 15m · last 04:47',
            status: 'cron',
            summary: 'no new activities'
        }),
```

- [ ] **Step 2: Update the research task mock in `ui/src/lib/mocks/task.ts`**

In `makeTaskList()`, replace the research task:

```typescript
        makeTask({
            id: '01KP000000000000000000RSRC',
            type: 'code',
            status: 'completed',
            title: 'Svelte 5 migration audit',
            completed_at: new Date(Date.now() - 3_600_000).toISOString(),
            result: {
                status: 'ok',
                pr: 'https://github.com/t-eckert/ardent-forge/pull/42'
            }
        }),
```

- [ ] **Step 3: Update `ui/src/lib/mocks/thread.ts`**

In `makeThread()`, change `preview`:

```typescript
        preview: 'weather · repos · code tasks',
```

Remove the `thread-purchases` entry from `makeThreadList()` — delete:

```typescript
        makeThread({
            id: 'thread-purchases',
            title: 'Weekly purchases review',
            preview: '$412.86 · groceries leading',
            kind: 'code+tools',
            lastActivityIso: daysAgoIso(6),
            unread: false,
            widgetCount: 1
        })
```

- [ ] **Step 4: Update `ui/src/lib/mocks/widgets/result.ts`**

Change the label from `'research output'` to `'code result'`.

---

### Task 9: Fix library, stores, and chrome

**Files:**
- Modify: `ui/src/lib/library/views/agents-roster.svelte`
- Modify: `ui/src/lib/library/views/connectors-roster.svelte`
- Modify: `ui/src/lib/library/index.ts`
- Modify: `ui/src/lib/stores/pinned.state.svelte.ts`
- Modify: `ui/src/lib/stores/sync.state.svelte.ts`
- Modify: `ui/src/lib/chrome/components/breadcrumb-strip.svelte`
- Modify: `ui/src/lib/chrome/components/breadcrumb-strip.stories.ts`

- [ ] **Step 1: Remove `research` from `badgeFor` in `ui/src/lib/library/views/agents-roster.svelte`**

```typescript
    function badgeFor(name: string): { label: string; tone: 'ink' | 'signal' | 'graphite' | 'ember' | 'warn' } {
        const map: Record<string, any> = {
            code: { label: '{}', tone: 'ink' },
            'code-agent': { label: '{}', tone: 'ink' },
            plan: { label: '§', tone: 'signal' },
            tickets: { label: '→', tone: 'ember' },
            echo: { label: '·', tone: 'graphite' }
        };
        return map[name] ?? { label: name[0]?.toUpperCase() ?? '?', tone: 'ink' };
    }
```

- [ ] **Step 2: Remove `strava` from `badgeFor` in `ui/src/lib/library/views/connectors-roster.svelte`**

```typescript
    function badgeFor(name: string): { label: string; tone: 'ember' | 'signal' | 'graphite' | 'ink' } {
        const map: Record<string, any> = {
            weather: { label: '☀', tone: 'ember' },
            github: { label: '{}', tone: 'ink' },
            linear: { label: 'L', tone: 'signal' },
            notebook: { label: '¶', tone: 'graphite' },
            osm: { label: '◎', tone: 'signal' },
            plaid: { label: '$', tone: 'ink' },
            uptime: { label: '↑', tone: 'graphite' }
        };
        return map[name] ?? { label: name[0]?.toUpperCase() ?? '?', tone: 'graphite' };
    }
```

- [ ] **Step 3: Verify `ui/src/lib/library/index.ts` needs no changes**

The file already exports only `LibraryIndex`, `AgentsRoster`, `ConnectorsRoster`, and `MemoryLibrary` — no field-related exports exist. Run:

```bash
cat ui/src/lib/library/index.ts
```

Expected output:
```typescript
export { default as LibraryIndex } from './views/library-index.svelte';
export { default as AgentsRoster } from './views/agents-roster.svelte';
export { default as ConnectorsRoster } from './views/connectors-roster.svelte';
export { default as MemoryLibrary } from './views/memory-library.svelte';
```

If it matches, no edit needed. Move on.

- [ ] **Step 4: Remove field pins from `ui/src/lib/stores/pinned.state.svelte.ts`**

```typescript
const DEFAULTS: PinnedItem[] = [
    { id: 'todays-log', label: "Today's log", href: '/library/log/today', kind: 'note' }
];
```

Also update the `kind` type — `'field'` is no longer a valid pin kind since fields are gone:

```typescript
export interface PinnedItem {
    id: string;
    label: string;
    href: string;
    kind: 'thread' | 'note' | 'agent';
}
```

- [ ] **Step 5: Remove strava from `ui/src/lib/stores/sync.state.svelte.ts`**

```typescript
const DEFAULTS: SourceSync[] = [
    { source: 'notebook', state: 'synced', lastSyncIso: iso(-2) },
    { source: 'linear', state: 'synced', lastSyncIso: iso(-6) },
    { source: 'github', state: 'live', lastSyncIso: iso(-1) },
    { source: 'calendar', state: 'synced', lastSyncIso: iso(-9) },
    { source: 'garmin', state: 'optional' }
];
```

- [ ] **Step 6: Update JSDoc comment in `ui/src/lib/chrome/components/breadcrumb-strip.svelte`**

Change the `rightMeta` prop comment from `"strava synced · 4m"` to `"notebook synced · 4m"`:

```typescript
        /** Right-side meta line (e.g. "notebook synced · 4m") */
        rightMeta?: string;
```

- [ ] **Step 7: Remove health/strava entries from `ui/src/lib/chrome/components/breadcrumb-strip.stories.ts`**

Remove any story args that reference `/library/fields/health` breadcrumbs or `rightMeta: 'strava synced · 4m'`. Replace with neutral equivalents (e.g. a library/memory trail, `rightMeta: 'notebook synced · 4m'`).

---

### Task 10: Fix agents, tasks, and API adapters

**Files:**
- Modify: `ui/src/lib/agents/components/agent-row.svelte`
- Modify: `ui/src/lib/tasks/components/task-row.svelte`
- Modify: `ui/src/lib/tasks/tasks.stories.ts`
- Modify: `ui/src/lib/api/adapters.test.ts`

- [ ] **Step 1: Remove `strava-pull` case from `badgeFor` in `ui/src/lib/agents/components/agent-row.svelte`**

```typescript
    function badgeFor(kind: AgentRun['kind']): { label: string; tone: 'ink' | 'signal' | 'graphite' | 'ember' | 'warn' } {
        switch (kind) {
            case 'code-agent':
                return { label: '{}', tone: 'ink' };
            case 'triage-agent':
                return { label: '⟲', tone: 'signal' };
            case 'notebook-sync':
                return { label: '¶', tone: 'graphite' };
            case 'ci-watcher':
                return { label: '▸', tone: 'ink' };
            case 'backup-agent':
                return { label: '!', tone: 'warn' };
            default:
                return { label: '·', tone: 'ink' };
        }
    }
```

- [ ] **Step 2: Remove `research` case from `badgeFor` in `ui/src/lib/tasks/components/task-row.svelte`**

```typescript
    function badgeFor(type: string): { label: string; tone: 'ink' | 'signal' | 'graphite' | 'ember' | 'warn' } {
        switch (type) {
            case 'code': return { label: '{}', tone: 'ink' };
            case 'plan': return { label: '◇', tone: 'signal' };
            case 'tickets': return { label: '#', tone: 'ember' };
            case 'echo': return { label: '·', tone: 'graphite' };
            default: return { label: '·', tone: 'graphite' };
        }
    }
```

- [ ] **Step 3: Remove the research task story from `ui/src/lib/tasks/tasks.stories.ts`**

Find and delete the story named `'Detail · completed research task'` (and its associated args/mock data). Keep all other stories.

- [ ] **Step 4: Update research fixtures in `ui/src/lib/api/adapters.test.ts`**

Find every occurrence of `type: 'research'` and change it to `type: 'code'`. Find every occurrence of `agent: 'research-agent'` and change it to `agent: 'code-agent'`. Update any assertion that checks for `'research'` or `'research-agent'` to check for `'code'` or `'code-agent'` respectively.

---

### Task 11: Final verification and commit

- [ ] **Step 1: Run backend tests**

```bash
uv run pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend type check**

```bash
cd ui && pnpm check
```

Expected: no type errors.

- [ ] **Step 3: Run frontend unit tests**

```bash
cd ui && pnpm test
```

Expected: all tests pass.

- [ ] **Step 4: Confirm no stray imports remain**

```bash
grep -rn "workout\|strava\|research\|purchases\|places.map\|fields-index\|FieldCard\|FieldsGrid\|pin-marker\|PinMarker\|todo\|Todo" \
  ui/src/lib ui/src/routes \
  --include="*.ts" --include="*.svelte" \
  | grep -v "node_modules\|\.svelte-kit\|adapters.test"
```

Review any hits. Residual mentions in comments or story descriptions are fine; any live import or type reference must be addressed.

- [ ] **Step 5: Commit**

```bash
git add -u ui/src/
git add ui/src/  # picks up deleted files
git commit -m "chore: remove life-management frontend (fields, workout, purchases, places-map, todos)"
```
