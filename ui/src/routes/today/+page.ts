import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';
import { adaptThread, adaptTaskToAgentRun } from '$lib/api/adapters';

export const ssr = false;

export const load: PageLoad = async () => {
	const [threads, tasks, repos, weather] = await Promise.all([
		api.threads
			.list()
			.then((raw) => raw.map((t) => adaptThread(t)))
			.catch(() => []),
		api.tasks.list().catch(() => []),
		api.repos.list().catch(() => []),
		api.weather.current().catch(() => null)
	]);

	const activeTasks = tasks.filter((t) =>
		['executing', 'triaging', 'verifying', 'delivering'].includes(t.status)
	);
	const queuedTasks = tasks.filter((t) => t.status === 'queued');
	const recentTasks = tasks
		.filter((t) => t.status === 'completed')
		.slice(0, 10)
		.map(adaptTaskToAgentRun);

	return { threads, activeTasks, queuedTasks, recentTasks, repos, weather };
};
