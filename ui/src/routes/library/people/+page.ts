import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;

export const load: PageLoad = async () => {
	const result = await api.notebook.list('People').catch(() => ({ path: 'People', entries: [] }));
	const people = result.entries
		.filter((e: string) => e.endsWith('.md'))
		.map((e: string) => e.replace(/\.md$/, ''))
		.sort();
	return { people };
};
