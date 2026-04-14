import { Todo, type Todo as TodoT } from '$lib/schemas/todo';

export function makeTodo(overrides: Partial<TodoT> = {}): TodoT {
	return Todo.parse({
		id: 'todo-1',
		title: 'Draft spec for tick interval patch',
		status: 'open',
		category: 'work',
		context: 'Coordinator',
		dueIso: new Date().toISOString(),
		...overrides
	});
}

export function makeTodaysTodos(): TodoT[] {
	return [
		makeTodo(),
		makeTodo({
			id: 'todo-2',
			title: 'Review agent PR: rename/t-client',
			status: 'review',
			category: 'review'
		}),
		makeTodo({ id: 'todo-3', title: 'Stretching · 15 min', status: 'open', category: 'health' }),
		makeTodo({
			id: 'todo-4',
			title: 'Pick up frame for Painting trip',
			status: 'open',
			category: 'errand'
		}),
		makeTodo({
			id: 'todo-5',
			title: 'Investigate coordinator backoff under load',
			status: 'open',
			category: 'work'
		}),
		makeTodo({
			id: 'todo-6',
			title: 'Reflect on wk 08 — notebook log',
			status: 'open',
			category: 'ritual'
		})
	];
}
