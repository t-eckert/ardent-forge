# Phase 2c — Frontend Steer Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the Phase 2a/2b steering endpoints in the task detail view so the operator can cancel, approve/reject at a gate, retry, follow up, and copy the Zellij attach command — with the view auto-refreshing while a task is active.

**Architecture:** Update the stale `Task` zod schema, add typed API client mutations for the five steer endpoints, build a status-aware `TaskSteerControls` component, render it in the task detail view, and add a polling `$effect` that re-runs the page load every 3s while the open task is non-terminal.

**Tech Stack:** SvelteKit 2, Svelte 5 (runes), TypeScript, Tailwind 4, zod, Vitest, Storybook (`@storybook/sveltekit` + `storybook/test`). All work is under `ui/`. Run commands from `ui/`.

**Spec:** `docs/superpowers/specs/2026-06-20-control-plane-phase2c-steer-controls-design.md`

---

## File Structure

**Modified:**
- `ui/src/lib/schemas/task.ts` — add statuses + two fields.
- `ui/src/lib/api/typed.ts` — add `cancel`/`approve`/`reject`/`retry`/`followUp` to `api.tasks`; export `ApiError` (already exported).
- `ui/src/lib/tasks/index.ts` — export the new component.
- `ui/src/lib/tasks/views/task-detail-view.svelte` — render controls + polling.

**Created:**
- `ui/src/lib/tasks/components/task-steer-controls.svelte`
- `ui/src/lib/tasks/components/task-steer-controls.stories.ts`
- `ui/src/lib/schemas/task.test.ts`
- `ui/src/lib/api/typed.test.ts`

---

### Task 1: Update the Task schema

**Files:**
- Modify: `ui/src/lib/schemas/task.ts` (TaskStatus enum ~line 14, Task object ~line 36)
- Test: `ui/src/lib/schemas/task.test.ts`

- [ ] **Step 1: Write the failing test**

Create `ui/src/lib/schemas/task.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { Task, TaskStatus } from './task';

const base = {
	id: '01HZX9MVT0EXAMPLE0000000000',
	type: 'code',
	status: 'queued',
	source: 'manual',
	title: 't',
	description: 'd',
	created_at: '2026-06-20T00:00:00+00:00',
	updated_at: '2026-06-20T00:00:00+00:00'
};

describe('Task schema — phase 2 statuses', () => {
	it('parses awaiting_approval', () => {
		const t = Task.parse({ ...base, status: 'awaiting_approval' });
		expect(t.status).toBe('awaiting_approval');
	});

	it('parses cancelled', () => {
		const t = Task.parse({ ...base, status: 'cancelled' });
		expect(t.status).toBe('cancelled');
	});

	it('round-trips require_approval and continues_task_id', () => {
		const t = Task.parse({
			...base,
			status: 'queued',
			require_approval: true,
			continues_task_id: '01HZX9MVT0PARENT00000000000'
		});
		expect(t.require_approval).toBe(true);
		expect(t.continues_task_id).toBe('01HZX9MVT0PARENT00000000000');
	});

	it('defaults require_approval to false when absent', () => {
		const t = Task.parse(base);
		expect(t.require_approval).toBe(false);
	});

	it('TaskStatus enum includes the new states', () => {
		expect(TaskStatus.options).toContain('awaiting_approval');
		expect(TaskStatus.options).toContain('cancelled');
	});
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm vitest run src/lib/schemas/task.test.ts`
Expected: FAIL — `awaiting_approval`/`cancelled` not in the enum; `require_approval` undefined.

- [ ] **Step 3: Update the enum**

In `ui/src/lib/schemas/task.ts`, extend `TaskStatus`:

```ts
export const TaskStatus = z.enum([
	'queued',
	'triaging',
	'executing',
	'verifying',
	'delivering',
	'completed',
	'failed',
	'awaiting_approval',
	'cancelled'
]);
```

- [ ] **Step 4: Add the two fields**

In the `Task = z.object({ ... })` definition, add (next to `retries`):

```ts
	retries: z.number().int().default(0),
	require_approval: z.boolean().default(false),
	continues_task_id: z.string().nullable().optional(),
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pnpm vitest run src/lib/schemas/task.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/lib/schemas/task.ts src/lib/schemas/task.test.ts
git commit -m "feat(ui): Task schema gains awaiting_approval/cancelled + require_approval/continues_task_id"
```

---

### Task 2: API client mutations

**Files:**
- Modify: `ui/src/lib/api/typed.ts` (the `tasks:` block in the `api` object)
- Test: `ui/src/lib/api/typed.test.ts`

- [ ] **Step 1: Write the failing test**

Create `ui/src/lib/api/typed.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

const { api, ApiError } = await import('./typed');

const task = {
	id: '01HZX9MVT0EXAMPLE0000000000',
	type: 'code',
	status: 'queued',
	source: 'manual',
	title: 't',
	description: 'd',
	handler_data: {},
	retries: 0,
	require_approval: false,
	created_at: '2026-06-20T00:00:00+00:00',
	updated_at: '2026-06-20T00:00:00+00:00'
};

function ok(data: unknown, status = 200) {
	return {
		ok: status >= 200 && status < 300,
		status,
		json: () => Promise.resolve(data),
		text: () => Promise.resolve(JSON.stringify(data))
	};
}

beforeEach(() => mockFetch.mockReset());

describe('api.tasks steer mutations', () => {
	it('cancel POSTs to the cancel endpoint', async () => {
		mockFetch.mockResolvedValueOnce(ok(task));
		await api.tasks.cancel('abc');
		expect(mockFetch).toHaveBeenCalledWith(
			'/api/tasks/abc/cancel',
			expect.objectContaining({ method: 'POST' })
		);
	});

	it('approve POSTs to the approve endpoint', async () => {
		mockFetch.mockResolvedValueOnce(ok(task));
		await api.tasks.approve('abc');
		expect(mockFetch).toHaveBeenCalledWith(
			'/api/tasks/abc/approve',
			expect.objectContaining({ method: 'POST' })
		);
	});

	it('reject POSTs to the reject endpoint', async () => {
		mockFetch.mockResolvedValueOnce(ok(task));
		await api.tasks.reject('abc');
		expect(mockFetch).toHaveBeenCalledWith(
			'/api/tasks/abc/reject',
			expect.objectContaining({ method: 'POST' })
		);
	});

	it('retry POSTs to the retry endpoint', async () => {
		mockFetch.mockResolvedValueOnce(ok(task));
		await api.tasks.retry('abc');
		expect(mockFetch).toHaveBeenCalledWith(
			'/api/tasks/abc/retry',
			expect.objectContaining({ method: 'POST' })
		);
	});

	it('followUp POSTs the prompt body and returns the new task', async () => {
		mockFetch.mockResolvedValueOnce(ok({ ...task, id: 'new-id', continues_task_id: 'abc' }));
		const created = await api.tasks.followUp('abc', 'do the thing');
		expect(mockFetch).toHaveBeenCalledWith(
			'/api/tasks/abc/follow-up',
			expect.objectContaining({ method: 'POST', body: JSON.stringify({ prompt: 'do the thing' }) })
		);
		expect(created.id).toBe('new-id');
	});

	it('throws ApiError on a 409', async () => {
		mockFetch.mockResolvedValueOnce({
			ok: false,
			status: 409,
			text: () => Promise.resolve('Cannot cancel a completed task')
		});
		await expect(api.tasks.cancel('abc')).rejects.toThrow(ApiError);
	});
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm vitest run src/lib/api/typed.test.ts`
Expected: FAIL — `api.tasks.cancel` is not a function.

- [ ] **Step 3: Add the mutations**

In `ui/src/lib/api/typed.ts`, inside the `tasks: { ... }` object (after `create`), add:

```ts
		cancel: (id: string) => request(`/api/tasks/${id}/cancel`, Task, { method: 'POST' }),
		approve: (id: string) => request(`/api/tasks/${id}/approve`, Task, { method: 'POST' }),
		reject: (id: string) => request(`/api/tasks/${id}/reject`, Task, { method: 'POST' }),
		retry: (id: string) => request(`/api/tasks/${id}/retry`, Task, { method: 'POST' }),
		followUp: (id: string, prompt: string) =>
			request(`/api/tasks/${id}/follow-up`, Task, {
				method: 'POST',
				body: JSON.stringify({ prompt })
			})
```

(`request` already sets the `Content-Type: application/json` header and throws `ApiError` on non-2xx. `ApiError` is already exported from this module.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm vitest run src/lib/api/typed.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/api/typed.ts src/lib/api/typed.test.ts
git commit -m "feat(ui): typed api mutations for cancel/approve/reject/retry/follow-up"
```

---

### Task 3: TaskSteerControls component

**Files:**
- Create: `ui/src/lib/tasks/components/task-steer-controls.svelte`
- Create: `ui/src/lib/tasks/components/task-steer-controls.stories.ts`
- Modify: `ui/src/lib/tasks/index.ts`

- [ ] **Step 1: Write the component**

Create `ui/src/lib/tasks/components/task-steer-controls.svelte`:

```svelte
<script lang="ts">
	import { invalidateAll, goto } from '$app/navigation';
	import type { Task } from '$lib/schemas/task';
	import { api, ApiError } from '$lib/api/typed';
	import { Button } from '$lib/components';
	import { Meta } from '$lib/typography';

	interface Props {
		task: Task;
	}

	let { task }: Props = $props();

	const ACTIVE = new Set(['queued', 'triaging', 'executing', 'verifying', 'delivering']);
	const isActive = $derived(ACTIVE.has(task.status));
	const isCode = $derived(task.type === 'code');
	const canFollowUp = $derived(
		isCode && ['completed', 'failed', 'awaiting_approval'].includes(task.status)
	);
	const session = $derived((task.handler_data?.zellij_session as string | undefined) ?? undefined);

	let busy = $state(false);
	let error = $state<string | null>(null);
	let confirming = $state<null | 'cancel' | 'reject'>(null);
	let confirmTimer: ReturnType<typeof setTimeout> | undefined;
	let showFollowUp = $state(false);
	let followUpPrompt = $state('');
	let copied = $state(false);

	async function run(fn: () => Promise<unknown>) {
		if (busy) return;
		busy = true;
		error = null;
		try {
			await fn();
			await invalidateAll();
		} catch (e) {
			error = e instanceof ApiError || e instanceof Error ? e.message : 'Action failed';
		} finally {
			busy = false;
		}
	}

	function arm(which: 'cancel' | 'reject') {
		if (confirming === which) {
			clearTimeout(confirmTimer);
			confirming = null;
			run(() => (which === 'cancel' ? api.tasks.cancel(task.id) : api.tasks.reject(task.id)));
			return;
		}
		confirming = which;
		clearTimeout(confirmTimer);
		confirmTimer = setTimeout(() => (confirming = null), 3000);
	}

	async function submitFollowUp() {
		const prompt = followUpPrompt.trim();
		if (!prompt || busy) return;
		busy = true;
		error = null;
		try {
			const created = await api.tasks.followUp(task.id, prompt);
			await goto(`/tasks/${created.id}`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Follow-up failed';
		} finally {
			busy = false;
		}
	}

	async function copyAttach() {
		const cmd =
			(task.handler_data?.attach_cmd as string | undefined) ??
			(session ? `ssh box -t zellij attach ${session}` : '');
		if (!cmd) return;
		try {
			await navigator.clipboard.writeText(cmd);
			copied = true;
			setTimeout(() => (copied = false), 1500);
		} catch {
			error = 'Clipboard unavailable';
		}
	}
</script>

{#if task.status !== 'cancelled'}
	<div class="px-10 py-4 border-b border-[var(--color-border)] flex flex-col gap-3">
		<div class="flex flex-wrap items-center gap-2">
			{#if isActive}
				<Button variant="danger" size="sm" disabled={busy} onclick={() => arm('cancel')}>
					{confirming === 'cancel' ? 'Confirm?' : 'Cancel'}
				</Button>
			{/if}
			{#if task.status === 'awaiting_approval'}
				<Button
					variant="primary"
					size="sm"
					disabled={busy}
					onclick={() => run(() => api.tasks.approve(task.id))}>Approve</Button
				>
				<Button variant="danger" size="sm" disabled={busy} onclick={() => arm('reject')}>
					{confirming === 'reject' ? 'Confirm?' : 'Reject'}
				</Button>
			{/if}
			{#if task.status === 'failed'}
				<Button
					variant="secondary"
					size="sm"
					disabled={busy}
					onclick={() => run(() => api.tasks.retry(task.id))}>Retry</Button
				>
			{/if}
			{#if canFollowUp}
				<Button variant="secondary" size="sm" disabled={busy} onclick={() => (showFollowUp = !showFollowUp)}
					>Follow up</Button
				>
			{/if}
			{#if session}
				<Button variant="ghost" size="sm" onclick={copyAttach}
					>{copied ? 'Copied' : 'Copy attach cmd'}</Button
				>
			{/if}
		</div>

		{#if showFollowUp}
			<div
				class="flex flex-col gap-2 p-3 bg-[var(--color-bench)] border border-[var(--color-border)] rounded-[8px]"
			>
				<textarea
					bind:value={followUpPrompt}
					aria-label="Follow-up prompt"
					rows="3"
					placeholder="Describe the follow-up work — it continues the same session"
					class="w-full resize-none bg-transparent text-sm text-[var(--color-ink)] outline-none placeholder:text-[var(--color-graphite)]"
				></textarea>
				<div class="flex items-center gap-2 justify-end">
					<Button
						variant="ghost"
						size="sm"
						onclick={() => {
							showFollowUp = false;
							followUpPrompt = '';
						}}>Close</Button
					>
					<Button
						variant="primary"
						size="sm"
						disabled={busy || !followUpPrompt.trim()}
						onclick={submitFollowUp}>Send</Button
					>
				</div>
			</div>
		{/if}

		{#if error}
			<Meta size="xs">{error}</Meta>
		{/if}
	</div>
{/if}
```

Note: the follow-up panel's close button is labelled **Close** (not "Cancel") so it never collides with the destructive **Cancel** action in tests or for the user.

- [ ] **Step 2: Export it**

In `ui/src/lib/tasks/index.ts`, add:

```ts
export { default as TaskSteerControls } from './components/task-steer-controls.svelte';
```

- [ ] **Step 3: Write the stories + interaction tests**

Create `ui/src/lib/tasks/components/task-steer-controls.stories.ts`:

```ts
import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import { expect, within, userEvent, spyOn } from 'storybook/test';
import TaskSteerControls from './task-steer-controls.svelte';

const baseTask = {
	id: '01HZX9MVT0EXAMPLE0000000000',
	type: 'code',
	status: 'queued',
	source: 'manual',
	title: 't',
	description: 'd',
	handler_data: {},
	result: null,
	retries: 0,
	require_approval: false,
	continues_task_id: null,
	created_at: '2026-06-20T00:00:00+00:00',
	updated_at: '2026-06-20T00:00:00+00:00',
	referenced_by_thread_ids: []
};

const meta = {
	title: 'Tasks/TaskSteerControls',
	component: TaskSteerControls
} satisfies Meta<ComponentProps<typeof TaskSteerControls>>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Active: Story = {
	args: { task: { ...baseTask, status: 'executing', handler_data: { zellij_session: 'agent-x' } } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await expect(canvas.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
		await expect(canvas.getByRole('button', { name: /attach/i })).toBeInTheDocument();
		await expect(canvas.queryByRole('button', { name: 'Approve' })).toBeNull();
	}
};

export const AwaitingApproval: Story = {
	args: { task: { ...baseTask, status: 'awaiting_approval' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await expect(canvas.getByRole('button', { name: 'Approve' })).toBeInTheDocument();
		await expect(canvas.getByRole('button', { name: 'Reject' })).toBeInTheDocument();
		await expect(canvas.getByRole('button', { name: 'Follow up' })).toBeInTheDocument();
	}
};

export const Failed: Story = {
	args: { task: { ...baseTask, status: 'failed' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await expect(canvas.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
		await expect(canvas.getByRole('button', { name: 'Follow up' })).toBeInTheDocument();
	}
};

export const Completed: Story = {
	args: { task: { ...baseTask, status: 'completed' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await expect(canvas.getByRole('button', { name: 'Follow up' })).toBeInTheDocument();
		await expect(canvas.queryByRole('button', { name: 'Cancel' })).toBeNull();
	}
};

export const CompletedNonCode: Story = {
	args: { task: { ...baseTask, type: 'echo', status: 'completed' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await expect(canvas.queryByRole('button', { name: 'Follow up' })).toBeNull();
	}
};

export const Cancelled: Story = {
	args: { task: { ...baseTask, status: 'cancelled' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await expect(canvas.queryByRole('button')).toBeNull();
	}
};

export const CancelRequiresTwoClicks: Story = {
	args: { task: { ...baseTask, status: 'executing' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		const fetchSpy = spyOn(window, 'fetch').mockResolvedValue({
			ok: true,
			status: 200,
			json: () => Promise.resolve(baseTask),
			text: () => Promise.resolve('{}')
		} as Response);
		try {
			await userEvent.click(canvas.getByRole('button', { name: 'Cancel' }));
			// First click only arms the confirm — no request issued yet.
			await expect(canvas.getByRole('button', { name: 'Confirm?' })).toBeInTheDocument();
			await expect(fetchSpy).not.toHaveBeenCalled();
			await userEvent.click(canvas.getByRole('button', { name: 'Confirm?' }));
			await expect(fetchSpy).toHaveBeenCalledWith(
				expect.stringContaining('/api/tasks/01HZX9MVT0EXAMPLE0000000000/cancel'),
				expect.objectContaining({ method: 'POST' })
			);
		} finally {
			fetchSpy.mockRestore();
		}
	}
};

export const ApproveCallsEndpoint: Story = {
	args: { task: { ...baseTask, status: 'awaiting_approval' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		const fetchSpy = spyOn(window, 'fetch').mockResolvedValue({
			ok: true,
			status: 200,
			json: () => Promise.resolve({ ...baseTask, status: 'delivering' }),
			text: () => Promise.resolve('{}')
		} as Response);
		try {
			await userEvent.click(canvas.getByRole('button', { name: 'Approve' }));
			await expect(fetchSpy).toHaveBeenCalledWith(
				expect.stringContaining('/api/tasks/01HZX9MVT0EXAMPLE0000000000/approve'),
				expect.objectContaining({ method: 'POST' })
			);
		} finally {
			fetchSpy.mockRestore();
		}
	}
};
```

`storybook/test` exports `spyOn`, `fn`, `userEvent`, `expect`, `within`, `waitFor`, `mocked` (verified against `storybook@^10.3.5`) — it does NOT export `vi`, which is why the spy uses `spyOn(window, 'fetch')`. The `invalidateAll()` call after a successful mutation is a harmless no-op in the Storybook environment (no router load to re-run); these assertions only verify the fetch was issued to the right endpoint.

- [ ] **Step 4: Run the component tests**

Run: `pnpm test`
Expected: the Storybook stories render and the `play` assertions pass. If `pnpm test` requires chromium and it is unavailable in this environment, run `pnpm check` (typecheck) instead and note that the Storybook tests must be run where chromium is available; do not block on a missing browser.

- [ ] **Step 5: Commit**

```bash
git add src/lib/tasks/components/task-steer-controls.svelte src/lib/tasks/components/task-steer-controls.stories.ts src/lib/tasks/index.ts
git commit -m "feat(ui): status-aware TaskSteerControls with two-step confirm + follow-up panel"
```

---

### Task 4: Wire controls + polling into the detail view

**Files:**
- Modify: `ui/src/lib/tasks/views/task-detail-view.svelte`

- [ ] **Step 1: Render the controls and add polling**

In `ui/src/lib/tasks/views/task-detail-view.svelte`, update the `<script>` to import the controls, `invalidateAll`, and add the polling effect. Replace the existing `<script lang="ts"> ... </script>` block with:

```svelte
<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import type { Task } from '$lib/schemas/task';
	import TaskList from '../components/task-list.svelte';
	import TaskHeader from '../components/task-header.svelte';
	import TaskStageStrip from '../components/task-stage-strip.svelte';
	import TaskSteerControls from '../components/task-steer-controls.svelte';
	import { Body, Eyebrow } from '$lib/typography';

	interface Props {
		tasks: Task[];
		active: Task;
	}

	let { tasks, active }: Props = $props();

	const handlerEntries = $derived(Object.entries(active.handler_data ?? {}));
	const resultEntries = $derived(active.result ? Object.entries(active.result) : []);

	// Poll while the open task is active so the stage strip advances and the
	// approval gate's buttons appear on their own. Stops at a terminal state.
	const TERMINAL = new Set(['completed', 'failed', 'cancelled']);
	$effect(() => {
		if (TERMINAL.has(active.status)) return;
		const t = setInterval(() => invalidateAll(), 3000);
		return () => clearInterval(t);
	});
</script>
```

- [ ] **Step 2: Add the controls to the markup**

In the same file, insert `<TaskSteerControls task={active} />` immediately after `<TaskStageStrip task={active} />`:

```svelte
		<TaskHeader task={active} />
		<TaskStageStrip task={active} />
		<TaskSteerControls task={active} />
```

- [ ] **Step 3: Typecheck**

Run: `pnpm check`
Expected: no new type errors. (`active.status` reads as the `TaskStatus` union; `TERMINAL.has` takes a string — fine.)

- [ ] **Step 4: Commit**

```bash
git add src/lib/tasks/views/task-detail-view.svelte
git commit -m "feat(ui): render steer controls + poll active task in detail view"
```

---

### Task 5: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Typecheck**

Run: `pnpm check`
Expected: PASS (0 errors). Fix any type errors surfaced by the new code before continuing.

- [ ] **Step 2: Unit tests**

Run: `pnpm vitest run`
Expected: PASS — including the new `task.test.ts` and `typed.test.ts`.

- [ ] **Step 3: Component/Storybook tests (if chromium available)**

Run: `pnpm test`
Expected: PASS. If chromium is unavailable in this environment, report that the Storybook interaction tests could not run here and must be verified in CI (which provides chromium); do not treat a missing-browser error as a code failure.

- [ ] **Step 4: Commit any fixups**

```bash
git add -A
git commit -m "test(ui): phase 2c verification fixups" || echo "nothing to commit"
```

---

## Notes for the implementer

- Svelte 5 runes only (`$state`/`$derived`/`$props`/`$effect`) — match the surrounding files; no `export let`, no Svelte 4 stores for local state.
- `task.handler_data` is typed `Record<string, unknown>` by the zod schema, so `zellij_session`/`attach_cmd` need a `as string | undefined` cast — that is intentional and already in the component code above.
- The `Button` primitive (`$lib/components`) spreads `HTMLButtonAttributes`, so `onclick`/`disabled` pass straight through. Variants available: `primary`, `secondary`, `ghost`, `danger`; sizes `sm`/`md`/`lg`.
- Do not remove the dead `origin_thread_id` / `referenced_by_thread_ids` fields from the schema — out of scope (they're optional and harmless).
- The backend endpoints already exist and are tested (Phase 2a/2b). This phase is UI-only; do not touch `forge/`.
- Run all commands from `ui/` (`cd ui` first).
