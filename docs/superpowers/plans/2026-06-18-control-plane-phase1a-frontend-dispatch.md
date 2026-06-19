# Control Plane Phase 1a — Frontend strip + dispatch form

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the in-app chat/threads UI and replace its task-creation role with a direct dispatch form, so the UI becomes a chat-free control plane that dispatches and monitors agent tasks.

**Architecture:** The only UI path that creates work today is the conversational composer (creates a thread → chat dispatches a task). This plan adds a direct `POST /api/tasks` create path (with a coordinator nudge so dispatched work starts immediately), a `DispatchForm` Svelte component, and makes the Tasks page the dispatch+monitor landing. It then deletes the `threads` route/module and strips every `threads` reference across `sidebar`, `today`, `palette`, `settings`, `task-header`, the API client, and adapters. The chat/threads **backend** endpoints are left in place (dead but harmless) and removed in Phase 1b.

**Tech Stack:** SvelteKit 2 / Svelte 5 (`$props`/`$state`), Tailwind 4, Zod, FastAPI, pytest, Vitest/Storybook, Playwright.

**Reference — this is the spec:** `docs/superpowers/specs/2026-06-18-dispatch-steer-control-plane-design.md`

**Scope notes / deliberate deviations from the spec:**
- The spec says "today folds into the Tasks landing." This plan instead makes **Tasks** the dispatch+monitor surface (the dispatch form lives there) while keeping **Today** as a threads-stripped dashboard. Fully folding/redirecting `/today` into `/tasks` is **deferred** — it's a larger UX decision that doesn't block a chat-free control plane. Flag for the reviewer.
- This is **Phase 1a (frontend)**. The chat/threads **backend** (`forge/api/chat.py`, `forge/api/threads.py`, the orchestrator chat machinery, `ThreadStore`, `post_resolution`, and the task↔thread linkage in `forge/api/tasks.py`) is intentionally left in place and removed in **Phase 1b**. Until then those endpoints exist but are unreferenced by the UI.

---

### Task 1: Backend — `MANUAL` task source + coordinator nudge on `POST /api/tasks`

The dispatch form posts to `POST /api/tasks`, which today hardcodes `source=TaskSource.CHAT` and does **not** nudge the coordinator (only the chat dispatch path nudges). Add a `MANUAL` source and make create nudge the coordinator so dispatched tasks start within seconds instead of waiting a full poll interval.

**Files:**
- Modify: `forge/models.py` (the `TaskSource` enum, currently lines 26-30)
- Modify: `forge/api/tasks.py` (create path + a new `set_coordinator`)
- Modify: `forge/main.py` (wire coordinator into tasks api)
- Test: `tests/test_api_dispatch.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_api_dispatch.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from forge.db import Database
from forge.main import create_app
from forge.api import tasks as tasks_api
from forge.store import TaskStore
from forge.models import TaskSource, TaskStatus


@pytest.fixture
async def client():
    db = Database(":memory:")
    await db.initialize()
    app = create_app(db=db)
    store = TaskStore(db)
    tasks_api.set_store(store)

    nudged = {"count": 0}

    class StubCoordinator:
        def nudge(self) -> None:
            nudged["count"] += 1

    tasks_api.set_coordinator(StubCoordinator())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, store, nudged
    await db.close()


async def test_create_task_uses_manual_source_and_nudges(client):
    c, store, nudged = client
    resp = await c.post(
        "/api/tasks",
        json={"type": "code", "title": "do a thing", "description": "the details", "repo": "t-eckert/x"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["source"] == "manual"
    assert body["status"] == TaskStatus.QUEUED.value
    saved = await store.get(body["id"])
    assert saved is not None
    assert saved.source == TaskSource.MANUAL
    assert nudged["count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_dispatch.py -v`
Expected: FAIL — `AttributeError: module 'forge.api.tasks' has no attribute 'set_coordinator'` (and/or `TaskSource` has no `MANUAL`).

- [ ] **Step 3: Add `MANUAL` to `TaskSource`**

In `forge/models.py`, the `TaskSource` enum currently reads:

```python
class TaskSource(StrEnum):
    LINEAR = "linear"
    CHAT = "chat"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
```

Add a `MANUAL` member:

```python
class TaskSource(StrEnum):
    LINEAR = "linear"
    CHAT = "chat"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    MANUAL = "manual"
```

- [ ] **Step 4: Add coordinator wiring + nudge to `forge/api/tasks.py`**

After the existing `_store` block near the top of `forge/api/tasks.py` (after `def get_store()`), add a coordinator holder:

```python
_coordinator: object | None = None


def set_coordinator(coordinator: object) -> None:
    global _coordinator
    _coordinator = coordinator
```

In `create_task`, change the hardcoded source from `TaskSource.CHAT` to `TaskSource.MANUAL`, and after `await store.save(task)` add the nudge (place it before the existing `ts = _thread_store(request)` block):

```python
    await store.save(task)

    if _coordinator is not None and hasattr(_coordinator, "nudge"):
        _coordinator.nudge()

    ts = _thread_store(request)
```

(Leave the `origin_thread_id` linkage code as-is for now; Phase 1b removes it.)

- [ ] **Step 5: Wire the coordinator into the tasks api in `forge/main.py`**

In `forge/main.py`, in the lifespan, immediately after `app.state.coordinator = coordinator` (currently line 312), add:

```python
        tasks.set_coordinator(coordinator)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_api_dispatch.py -v`
Expected: PASS.

- [ ] **Step 7: Run the broader API suite to confirm no regression**

Run: `uv run pytest tests/test_api.py -q`
Expected: all pass (the create path still returns 201 with the same shape, now `source: "manual"`).

- [ ] **Step 8: Commit**

```bash
git add forge/models.py forge/api/tasks.py forge/main.py tests/test_api_dispatch.py
git commit -m "feat(api): MANUAL task source + coordinator nudge on POST /api/tasks"
```

---

### Task 2: API client — add `api.tasks.create`

`src/lib/api/typed.ts` exposes `api.tasks.list` and `api.tasks.get` but no create. Add a create call the dispatch form will use.

**Files:**
- Modify: `ui/src/lib/api/typed.ts` (the `tasks:` block, currently ~lines 227-235)

- [ ] **Step 1: Add `create` to the `tasks` client block**

In `ui/src/lib/api/typed.ts`, the `tasks` block currently looks like:

```ts
	tasks: {
		list: (params?: { status?: string; type?: string }) => {
			const suffix = ... ;
			return request(`/api/tasks${suffix}`, z.array(Task));
		},
		get: (id: string) => request(`/api/tasks/${id}`, Task)
	},
```

Add a `create` method (keep `list` and `get` exactly as they are):

```ts
		create: (input: { type: string; title: string; description: string; repo?: string | null }) =>
			request('/api/tasks', Task, {
				method: 'POST',
				body: JSON.stringify(input)
			}),
```

This matches the confirmed helper signature `request<T>(path, schema, init?: RequestInit)` and the existing POST pattern used by `repos.clone` (`request('/api/repos/clone', Repo, { method: 'POST', body: JSON.stringify({ url }) })`). The shared `request` helper already sets the `Content-Type: application/json` header.

- [ ] **Step 2: Verify it typechecks**

Run: `cd ui && pnpm check`
Expected: 0 errors attributable to `typed.ts` (pre-existing unrelated warnings OK).

- [ ] **Step 3: Commit**

```bash
git add ui/src/lib/api/typed.ts
git commit -m "feat(ui): api.tasks.create"
```

---

### Task 3: Build the `DispatchForm` component

A direct task-dispatch form: pick a repo, pick an agent (default Code), write the prompt, fire → create the task → navigate to its detail page. Modeled on the existing `today/components/composer.svelte` structure, but creating a task instead of a thread.

**Files:**
- Create: `ui/src/lib/tasks/components/dispatch-form.svelte`
- Create: `ui/src/lib/tasks/components/dispatch-form.stories.ts`

- [ ] **Step 1: Write the component**

Create `ui/src/lib/tasks/components/dispatch-form.svelte`:

```svelte
<script lang="ts">
	import { goto } from '$app/navigation';
	import { Eyebrow, Meta } from '$lib/typography';
	import { api } from '$lib/api/typed';
	import type { Repo } from '$lib/api/typed';

	interface Props {
		repos?: Repo[];
		agentTypes?: string[];
	}

	let { repos = [], agentTypes = ['code', 'plan', 'echo'] }: Props = $props();

	let prompt = $state('');
	let repo = $state<string>('');
	let agentType = $state<string>('code');
	let sending = $state(false);
	let error = $state<string | null>(null);

	async function submit() {
		const description = prompt.trim();
		if (!description || sending) return;
		sending = true;
		error = null;
		try {
			const title = description.length > 60 ? description.slice(0, 57) + '…' : description;
			const task = await api.tasks.create({
				type: agentType,
				title,
				description,
				repo: repo || null
			});
			await goto(`/tasks/${task.id}`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to dispatch task';
			sending = false;
		}
	}

	function onkey(e: KeyboardEvent) {
		if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			submit();
		}
	}
</script>

<div
	class="flex flex-col gap-2.5 p-4 bg-[var(--color-bench)] border border-[var(--color-border)] rounded-[8px]"
>
	<Eyebrow>DISPATCH A TASK</Eyebrow>
	<textarea
		bind:value={prompt}
		onkeydown={onkey}
		placeholder="Describe the work — e.g. 'add a /health/ready endpoint and a test'"
		rows="3"
		class="w-full resize-none bg-transparent text-sm text-[var(--color-ink)] outline-none placeholder:text-[var(--color-graphite)]"
	></textarea>
	<div class="flex items-center gap-2">
		<select
			bind:value={repo}
			class="bg-[var(--color-paper)] border border-[var(--color-border)] rounded px-2 py-1 text-[12px]"
		>
			<option value="">(no repo)</option>
			{#each repos as r (r.name)}
				<option value={r.name}>{r.name}</option>
			{/each}
		</select>
		<select
			bind:value={agentType}
			class="bg-[var(--color-paper)] border border-[var(--color-border)] rounded px-2 py-1 text-[12px]"
		>
			{#each agentTypes as a (a)}
				<option value={a}>{a}</option>
			{/each}
		</select>
		<div class="flex-1"></div>
		<button
			onclick={submit}
			disabled={sending || !prompt.trim()}
			class="bg-[var(--color-ember)] text-[var(--color-paper)] rounded px-3 py-1 text-[12px] font-medium disabled:opacity-50"
		>
			{sending ? 'Dispatching…' : 'Dispatch'}
		</button>
	</div>
	{#if error}
		<Meta size="xs">{error}</Meta>
	{/if}
</div>
```

- [ ] **Step 2: Write a Storybook story**

Create `ui/src/lib/tasks/components/dispatch-form.stories.ts`:

```ts
import type { Meta, StoryObj } from '@storybook/svelte';
import DispatchForm from './dispatch-form.svelte';

const meta = {
	title: 'Tasks/DispatchForm',
	component: DispatchForm
} satisfies Meta<DispatchForm>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		repos: [
			{ name: 't-eckert/ardent-forge', default_branch: 'main' } as never,
			{ name: 't-eckert/dotfiles', default_branch: 'main' } as never
		]
	}
};

export const NoRepos: Story = {
	args: { repos: [] }
};
```

- [ ] **Step 3: Export from the tasks barrel if one exists**

Run: `cat ui/src/lib/tasks/index.ts`
If the file exists and exports components, add:

```ts
export { default as DispatchForm } from './components/dispatch-form.svelte';
```

If there is no `index.ts`, skip this step and import the component by its direct path in Task 4.

- [ ] **Step 4: Verify it renders / typechecks**

Run: `cd ui && pnpm check`
Expected: 0 errors attributable to `dispatch-form.svelte` or its story.

- [ ] **Step 5: Commit**

```bash
git add ui/src/lib/tasks/components/dispatch-form.svelte ui/src/lib/tasks/components/dispatch-form.stories.ts ui/src/lib/tasks/index.ts
git commit -m "feat(ui): DispatchForm component"
```

---

### Task 4: Put the dispatch form on the Tasks page

Mount `DispatchForm` at the top of the Tasks landing, fed with the repo list and the agent-type list.

**Files:**
- Modify: `ui/src/routes/tasks/+page.svelte`
- Modify: `ui/src/routes/tasks/+page.ts`

- [ ] **Step 1: Add repos to the tasks loader**

The loader currently is:

```ts
import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';
import type { Task } from '$lib/schemas/task';

export const ssr = false;

const FALLBACK: Task[] = [];

export const load: PageLoad = async () => {
	try {
		return { tasks: await api.tasks.list() };
	} catch (err) {
		console.warn('/api/tasks unavailable', err);
		return { tasks: FALLBACK, apiError: String(err) };
	}
};
```

Replace the `load` body so repos are fetched alongside tasks (repos fail soft to `[]`):

```ts
export const load: PageLoad = async () => {
	const repos = await api.repos.list().catch(() => []);
	try {
		return { tasks: await api.tasks.list(), repos };
	} catch (err) {
		console.warn('/api/tasks unavailable', err);
		return { tasks: FALLBACK, repos, apiError: String(err) };
	}
};
```

- [ ] **Step 2: Render the form above the task list**

The page currently is:

```svelte
<script lang="ts">
	import { TaskListView } from '$lib/tasks';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

<TaskListView tasks={data.tasks} />
```

Replace it with the dispatch form mounted above the list:

```svelte
<script lang="ts">
	import { TaskListView, DispatchForm } from '$lib/tasks';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

<div class="flex flex-col gap-7 px-14 pt-9 max-w-[1440px] mx-auto">
	<DispatchForm repos={data.repos ?? []} />
	<TaskListView tasks={data.tasks} />
</div>
```

(If Task 3 Step 3 found no `ui/src/lib/tasks/index.ts` barrel, import `DispatchForm` from its direct path `$lib/tasks/components/dispatch-form.svelte` instead.)

- [ ] **Step 4: Verify**

Run: `cd ui && pnpm check`
Expected: 0 errors attributable to the tasks route.

- [ ] **Step 5: Commit**

```bash
git add ui/src/routes/tasks/+page.svelte ui/src/routes/tasks/+page.ts
git commit -m "feat(ui): dispatch form on the Tasks landing"
```

---

### Task 5: Remove Threads from the sidebar nav

**Files:**
- Modify: `ui/src/lib/chrome/components/sidebar.svelte` (the Threads `SpineItem`, currently lines 52-56)
- Modify: `ui/src/lib/chrome/components/sidebar.stories.ts` (if it asserts a Threads item)

- [ ] **Step 1: Delete the Threads spine item**

In `ui/src/lib/chrome/components/sidebar.svelte`, remove the entire `SpineItem` block for Threads:

```svelte
	<SpineItem href="/threads" label="Threads" icon={ChatCircle} active={active === 'threads'}>
		...
	</SpineItem>
```

Remove the now-unused `ChatCircle` import from that file if nothing else uses it (check first with a search within the file).

- [ ] **Step 2: Fix the story if needed**

Run: `grep -n "thread\|Threads\|ChatCircle" ui/src/lib/chrome/components/sidebar.stories.ts`
If any line references threads, remove it.

- [ ] **Step 3: Verify**

Run: `cd ui && pnpm check`
Expected: 0 errors attributable to the sidebar or its story.

- [ ] **Step 4: Commit**

```bash
git add ui/src/lib/chrome/components/sidebar.svelte ui/src/lib/chrome/components/sidebar.stories.ts
git commit -m "refactor(ui): drop Threads from sidebar nav"
```

---

### Task 6: Strip threads out of the Today view + loader

The Today view renders an `OpenThreads` panel and the loader fetches threads. Remove both. Keep everything else (daily log, active/queued/recent tasks, weather, repos).

**Files:**
- Modify: `ui/src/lib/today/views/today-view.svelte`
- Modify: `ui/src/routes/today/+page.ts`
- Modify: `ui/src/lib/today/index.ts`
- Delete: `ui/src/lib/today/components/open-threads.svelte`
- Delete: `ui/src/lib/today/components/composer.svelte` (chat composer — superseded by DispatchForm)

- [ ] **Step 1: Remove threads from `today-view.svelte`**

In `ui/src/lib/today/views/today-view.svelte`:
- Remove the import `import { OpenThreads } from '$lib/today';`
- Remove the import `import type { Thread } from '$lib/schemas/thread';`
- Remove `threads?: Thread[];` from the `Props` interface and `threads = [],` from the destructured props.
- Remove the `<!-- Open threads -->` block (`<OpenThreads {threads} />`) at the bottom of the right column.

- [ ] **Step 2: Remove threads from the Today loader**

In `ui/src/routes/today/+page.ts`:
- Remove the `api.threads.list()...` entry from the `Promise.all([...])` and the `threads` destructure target.
- Remove `adaptThread` from the `import { adaptThread, adaptTaskToAgentRun } from '$lib/api/adapters';` (keep `adaptTaskToAgentRun`).
- Remove `threads` from the returned object.

Resulting load (for reference):

```ts
const [tasks, repos, weather, dailyLog] = await Promise.all([
	api.tasks.list().catch(() => []),
	api.repos.list().catch(() => []),
	api.weather.current().catch(() => null),
	api.notebook.read(`Log/${todayDate}.md`).catch(() => null)
]);
// ...filters unchanged...
return { activeTasks, queuedTasks, recentTasks, repos, weather, dailyLog, todayDate };
```

- [ ] **Step 3: Update the today barrel**

In `ui/src/lib/today/index.ts`, remove the `OpenThreads` and `Composer` exports, leaving only `TodayView`:

```ts
export { default as TodayView } from './views/today-view.svelte';
```

- [ ] **Step 4: Delete the dead components**

```bash
git rm ui/src/lib/today/components/open-threads.svelte ui/src/lib/today/components/composer.svelte
```

- [ ] **Step 5: Verify**

Run: `cd ui && pnpm check`
Expected: 0 errors. If `pnpm check` flags a story for `composer`/`open-threads`, delete that story file too (`git rm`).

- [ ] **Step 6: Commit**

```bash
git add -A ui/src/lib/today ui/src/routes/today
git commit -m "refactor(ui): remove threads/composer from Today"
```

---

### Task 7: Strip residual threads references (palette, settings, task-header)

**Files:**
- Modify: `ui/src/lib/palette/types.ts`, `ui/src/lib/palette/components/result-row.svelte`, `ui/src/lib/palette/components/palette-overlay.svelte`
- Modify: `ui/src/lib/settings/views/settings-view.svelte` (line 34)
- Modify: `ui/src/lib/tasks/components/task-header.svelte` (line 24)

- [ ] **Step 1: Remove the `'thread'` palette result class**

- `ui/src/lib/palette/types.ts:5` — change `export type ResultClass = 'note' | 'task' | 'thread' | 'action';` to `export type ResultClass = 'note' | 'task' | 'action';`
- `ui/src/lib/palette/components/result-row.svelte:17` — remove the `thread: { icon: ChatCircle, bg: '...' },` entry from the icon/bg map; remove the now-unused `ChatCircle` import if nothing else in the file uses it.
- `ui/src/lib/palette/components/palette-overlay.svelte` — remove `thread: 'THREADS',` from the label map (line ~30) and remove `'thread'` from the `order` array (line ~34). Remove the `open in new thread` keycap hint line (~99) — replace that affordance with nothing (the default Enter behavior remains).

- [ ] **Step 2: Fix the settings label**

`ui/src/lib/settings/views/settings-view.svelte:34` — change the string `'Default agent for new threads'` to `'Default agent for dispatched tasks'`.

- [ ] **Step 3: Remove the origin-thread link from the task header**

`ui/src/lib/tasks/components/task-header.svelte:24` — delete the conditional fragment:

```svelte
{#if task.origin_thread_id} · thread <a href="/threads/{task.origin_thread_id}" class="underline">{task.origin_thread_id.slice(0, 8)}</a>{/if}
```

- [ ] **Step 4: Verify**

Run: `cd ui && pnpm check`
Expected: 0 errors attributable to these files.

- [ ] **Step 5: Commit**

```bash
git add ui/src/lib/palette ui/src/lib/settings ui/src/lib/tasks/components/task-header.svelte
git commit -m "refactor(ui): strip residual threads references"
```

---

### Task 8: Delete the threads route, module, schema, and API client surface

With nothing referencing threads anymore, delete the route, the `lib/threads` module, the thread schema, the thread adapters, and the `chat`/`threads` blocks from the API client.

**Files:**
- Delete: `ui/src/routes/threads/` (all four files)
- Delete: `ui/src/lib/threads/` (entire module)
- Delete: `ui/src/lib/schemas/thread.ts`
- Modify: `ui/src/lib/api/adapters.ts` (remove `adaptThread`, `adaptThreadDetail`, `adaptMessage`, and the `thread` schema imports)
- Modify: `ui/src/lib/api/typed.ts` (remove the `chat` block, the `threads` block, and the `BackendThread*` schemas + their exports)

- [ ] **Step 1: Delete the route and module**

```bash
git rm -r ui/src/routes/threads ui/src/lib/threads ui/src/lib/schemas/thread.ts
```

- [ ] **Step 2: Remove thread adapters**

In `ui/src/lib/api/adapters.ts`, remove `adaptThread`, `adaptThreadDetail`, `adaptMessage`, and the `import ... from '$lib/schemas/thread'` and `BackendThread*` type imports. Keep `adaptTaskToAgentRun` and any non-thread adapters.

- [ ] **Step 3: Remove chat + threads from the API client**

In `ui/src/lib/api/typed.ts`:
- Remove the `chat: { send: ... }` block (~lines 170-179).
- Remove the `threads: { list/get/create }` block (~lines 217-225).
- Remove the `BackendThread`, `BackendThreadDetail`, `BackendThreadList`, `BackendTaskSummary` zod schemas and any `export type` lines derived from them (search the file for `Thread` and remove the thread-only definitions). Keep `Task` and everything non-thread.

- [ ] **Step 4: Find any remaining references**

Run: `grep -rn "thread\|Thread\|/api/chat\|api.chat" ui/src --include=*.svelte --include=*.ts | grep -v "_stories\|mocks"`
Expected: no matches in non-story/non-mock source. If a match remains, remove it (or its story/mock). Clean up `ui/src/lib/*/mocks` and `_stories` thread fixtures only if `pnpm check`/`pnpm test` fail because of them.

- [ ] **Step 5: Verify typecheck + build**

Run: `cd ui && pnpm check && pnpm build`
Expected: `pnpm check` 0 errors (1 pre-existing `markdown.svelte` warning OK); `pnpm build` completes.

- [ ] **Step 6: Commit**

```bash
git add -A ui/src
git commit -m "refactor(ui): delete threads route, module, schema, and chat/threads API client"
```

---

### Task 9: Tests — dispatch form story interaction + smoke repoint

This repo has **no testing-library**; component tests run as Storybook stories through the vitest `storybook` project (see `ui/vite.config.ts`). The `DispatchForm` story from Task 3 already renders as a test. Add a `play` interaction assertion to it, and repoint the Playwright smoke off `/threads`.

**Files:**
- Modify: `ui/src/lib/tasks/components/dispatch-form.stories.ts`
- Modify: `ui/e2e/smoke.spec.ts` (and `ui/e2e/visual.spec.ts` if it references threads)

- [ ] **Step 1: Add a `play` assertion to the DispatchForm story**

Append to `ui/src/lib/tasks/components/dispatch-form.stories.ts`:

```ts
import { expect, within } from 'storybook/test';

export const DisabledWhenEmpty: Story = {
	args: { repos: [{ name: 't-eckert/x', default_branch: 'main' } as never] },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await expect(canvas.getByText('DISPATCH A TASK')).toBeInTheDocument();
		await expect(canvas.getByRole('button', { name: /Dispatch/i })).toBeDisabled();
		await expect(canvas.getByRole('option', { name: 't-eckert/x' })).toBeInTheDocument();
	}
};
```

(Confirm the import path for `expect`/`within` by checking an existing `*.stories.ts` that uses `play` — e.g. under `ui/src/lib/palette/_stories` or `ui/src/lib/widgets/_stories`. Match whatever import those use; the rest of the assertion stands.)

- [ ] **Step 2: Run the Storybook test project**

Run: `cd ui && pnpm test`
Expected: passes, including the new `DispatchForm` story play test. (Requires chromium; if unavailable, note it and rely on `pnpm check`.)

- [ ] **Step 3: Repoint the Playwright smoke off threads**

Run: `grep -rn "threads\|/threads\|chat" ui/e2e`
For any match in `ui/e2e/smoke.spec.ts` (or `visual.spec.ts`) that navigates to `/threads` or asserts a Threads nav item, repoint it to `/tasks` and assert the dispatch form is visible, e.g.:

```ts
await page.goto('/tasks');
await expect(page.getByText('DISPATCH A TASK')).toBeVisible();
```

If `ui/e2e` has no threads references, make no change here.

- [ ] **Step 4: Run the e2e smoke (best-effort)**

Run: `cd ui && pnpm test:e2e`
Expected: passes (Playwright falls back to mock data when the API is unreachable, per existing convention). If chromium is unavailable, note it and rely on `pnpm check` + the Storybook test.

- [ ] **Step 5: Commit**

```bash
git add ui/src/lib/tasks/components/dispatch-form.stories.ts ui/e2e
git commit -m "test(ui): dispatch form story interaction + repoint smoke off threads"
```

---

### Task 10: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Backend suite**

Run: `uv run pytest -q`
Expected: all pass. (Chat/threads backend tests still exist and still pass — those endpoints are removed in Phase 1b.)

- [ ] **Step 2: Frontend typecheck + unit/Storybook tests**

Run: `cd ui && pnpm check && pnpm test`
Expected: `pnpm check` 0 errors (1 pre-existing `markdown.svelte` warning OK); `pnpm test` passes.

- [ ] **Step 3: Production build**

Run: `cd ui && pnpm build`
Expected: completes successfully.

- [ ] **Step 4: Manual smoke (best-effort, on the box or via proxy)**

Start the backend (`uv run forge`) and the UI (`cd ui && pnpm dev`), open `/tasks`, dispatch a task with a repo + prompt, and confirm it appears in the task list and navigates to the detail page. The sidebar shows no Threads item; `/threads` 404s. This step is manual and not gating for merge.
