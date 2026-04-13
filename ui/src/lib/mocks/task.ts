import { Task, type Task as TaskT } from '$lib/schemas/task';

export function makeTask(overrides: Partial<TaskT> = {}): TaskT {
	return Task.parse({
		id: 'task-1',
		title: 'Draft spec for tick interval patch',
		status: 'open',
		category: 'work',
		context: 'Coordinator',
		dueIso: new Date().toISOString(),
		...overrides
	});
}

export function makeTodaysTasks(): TaskT[] {
	return [
		makeTask(),
		makeTask({
			id: 'task-2',
			title: 'Review agent PR: rename/t-client',
			status: 'review',
			category: 'review'
		}),
		makeTask({ id: 'task-3', title: 'Stretching · 15 min', status: 'open', category: 'health' }),
		makeTask({
			id: 'task-4',
			title: 'Pick up frame for Painting trip',
			status: 'open',
			category: 'errand'
		}),
		makeTask({
			id: 'task-5',
			title: 'Investigate coordinator backoff under load',
			status: 'open',
			category: 'work'
		}),
		makeTask({
			id: 'task-6',
			title: 'Reflect on wk 08 — notebook log',
			status: 'open',
			category: 'ritual'
		})
	];
}
