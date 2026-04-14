import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;

export const load: PageLoad = async ({ params }) => {
	try {
		const [tasks, active] = await Promise.all([
			api.tasks.list(),
			api.tasks.get(params.id).catch(() => null)
		]);
		return { tasks, active };
	} catch (err) {
		console.warn('/api/tasks unavailable', err);
		return { tasks: [], active: null, apiError: String(err) };
	}
};
