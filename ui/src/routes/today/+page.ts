import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';
import { adaptThread, adaptTaskToAgentRun } from '$lib/api/adapters';

export const ssr = false;

export const load: PageLoad = async () => {
	const [threads, weather, runs, todos] = await Promise.all([
		api.threads
			.list()
			.then((raw) => raw.map((t) => adaptThread(t)))
			.catch(() => []),
		api.weather.current().catch(() => null),
		api.tasks
			.list()
			.then((tasks) => tasks.slice(0, 20).map(adaptTaskToAgentRun))
			.catch(() => []),
		api.todos
			.list('today')
			.catch(() => [])
	]);

	// Yesterday summary: count tasks completed since yesterday midnight.
	const yesterday = new Date();
	yesterday.setDate(yesterday.getDate() - 1);
	yesterday.setHours(0, 0, 0, 0);
	const yesterdayTasks = await api.tasks
		.list({ status: 'completed' })
		.then((tasks) =>
			tasks.filter((t) => t.completed_at && new Date(t.completed_at) >= yesterday)
		)
		.catch(() => []);
	const carryOver = await api.tasks
		.list({ status: 'queued' })
		.then((tasks) => tasks.length)
		.catch(() => 0);

	const yesterdayRows = [
		{ label: 'Done', value: `${yesterdayTasks.length} task${yesterdayTasks.length !== 1 ? 's' : ''}` },
		{ label: 'Carry-over', value: String(carryOver) }
	];

	return { threads, weather, runs, todos, yesterdayRows };
};
