import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;

export const load: PageLoad = async () => {
	const result = await api.notebook.list('Log').catch(() => ({ path: 'Log', entries: [] }));
	// Filter to date-shaped entries and sort newest first.
	const entries = result.entries
		.filter((e: string) => e.endsWith('.md') && /^\d{4}-\d{2}-\d{2}/.test(e))
		.map((e: string) => e.replace(/\.md$/, ''))
		.sort()
		.reverse();
	return { entries };
};
