import type { LayoutLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;
export const prerender = false;

/**
 * Fetch lightweight counts for the sidebar spine chrome. Each lookup is
 * independent and tolerant of failure — the UI falls back to blank
 * indicators if the backend isn't reachable.
 */
export const load: LayoutLoad = async () => {
	const tasks = await api.tasks.list().catch(() => []);
	const tasksActive = tasks.filter(
		(t) => !['completed', 'failed'].includes(t.status)
	).length;
	return {
		chrome: {
			tasksActive
		}
	};
};
