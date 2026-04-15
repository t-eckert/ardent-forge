import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';
import { adaptTaskToAgentRun } from '$lib/api/adapters';

export const ssr = false;

const FALLBACK = [
	{ name: 'echo', task_type: 'echo', stages: ['execute'], connectors: [] as string[] }
];

export const load: PageLoad = async () => {
	const [agents, recentRuns] = await Promise.all([
		api.agents.list().catch(() => FALLBACK),
		api.tasks
			.list()
			.then((tasks) => tasks.slice(0, 20).map(adaptTaskToAgentRun))
			.catch(() => [])
	]);
	return { agents, recentRuns };
};
