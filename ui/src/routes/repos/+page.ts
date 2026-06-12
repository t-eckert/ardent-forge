import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;

export const load: PageLoad = async () => {
	const [repos, projects] = await Promise.all([
		api.repos.list().catch(() => []),
		api.projects.list().catch(() => [])
	]);
	return { repos, projects };
};
