import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';
import { adaptTaskToAgentRun } from '$lib/api/adapters';

export const ssr = false;

export const load: PageLoad = async () => {
	const todayDate = new Date().toISOString().slice(0, 10);

	const [tasks, repos, weather, dailyLog] = await Promise.all([
		api.tasks.list().catch(() => []),
		api.repos.list().catch(() => []),
		api.weather.current().catch(() => null),
		api.notebook.read(`Log/${todayDate}.md`).catch(() => null)
	]);

	const activeTasks = tasks.filter((t) =>
		['executing', 'triaging', 'verifying', 'delivering'].includes(t.status)
	);
	const queuedTasks = tasks.filter((t) => t.status === 'queued');
	const recentTasks = tasks
		.filter((t) => t.status === 'completed')
		.slice(0, 10)
		.map(adaptTaskToAgentRun);

	return { activeTasks, queuedTasks, recentTasks, repos, weather, dailyLog, todayDate };
};
