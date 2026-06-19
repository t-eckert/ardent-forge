import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';
import type { Task } from '$lib/schemas/task';

export const ssr = false;

const FALLBACK: Task[] = [];

export const load: PageLoad = async () => {
	const repos = await api.repos.list().catch(() => []);
	try {
		return { tasks: await api.tasks.list(), repos };
	} catch (err) {
		console.warn('/api/tasks unavailable', err);
		return { tasks: FALLBACK, repos, apiError: String(err) };
	}
};
