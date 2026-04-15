import type { Task } from '$lib/schemas/task';

export function makeTask(overrides: Partial<Task> = {}): Task {
	const now = new Date().toISOString();
	return {
		id: '01KP000000000000000000TASK',
		type: 'code',
		status: 'queued',
		source: 'chat',
		source_id: null,
		repo: 't-eckert/ardent-forge',
		title: 'Rename tClient across coordinator package',
		description:
			'Swap the identifier across every caller, keeping the existing test suite green.',
		handler_data: {},
		result: null,
		retries: 0,
		created_at: now,
		updated_at: now,
		completed_at: null,
		origin_thread_id: 'thread-abc123',
		referenced_by_thread_ids: [],
		...overrides
	};
}

export function makeTaskList(): Task[] {
	return [
		makeTask({
			id: '01KP000000000000000000CODE',
			type: 'code',
			status: 'executing',
			title: 'Rename tClient across coordinator package'
		}),
		makeTask({
			id: '01KP000000000000000000PLAN',
			type: 'plan',
			status: 'verifying',
			title: 'Spec the notebook connector'
		}),
		makeTask({
			id: '01KP000000000000000000RSRC',
			type: 'research',
			status: 'completed',
			title: 'Svelte 5 breaking changes',
			completed_at: new Date(Date.now() - 3_600_000).toISOString(),
			result: {
				status: 'ok',
				files: ['Wiki/Svelte 5 Breaking Changes.md'],
				source_url: 'https://svelte.dev/docs/svelte/v5-migration-guide'
			}
		}),
		makeTask({
			id: '01KP000000000000000000TCKT',
			type: 'tickets',
			status: 'failed',
			title: 'Triage stale Linear tickets'
		}),
		makeTask({
			id: '01KP000000000000000000ECHO',
			type: 'echo',
			status: 'queued',
			title: 'Echo smoke test'
		})
	];
}
