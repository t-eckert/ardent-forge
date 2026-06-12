import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;

export const load: PageLoad = async () => {
	const repos = await api.repos.list().catch(() => []);
	return { repos };
};
