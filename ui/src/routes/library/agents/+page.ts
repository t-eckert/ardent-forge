import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;

const FALLBACK = [
	{ name: 'echo', task_type: 'echo', stages: ['execute'], connectors: [] as string[] }
];

export const load: PageLoad = async () => {
	try {
		return { agents: await api.agents.list() };
	} catch (err) {
		console.warn('/api/agents unavailable — using fallback', err);
		return { agents: FALLBACK, apiError: String(err) };
	}
};
