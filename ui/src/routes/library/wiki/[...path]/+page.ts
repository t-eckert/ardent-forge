import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;

export const load: PageLoad = async ({ params }) => {
	const path = params.path;
	// Try as a file first, then as a directory.
	const page = await api.notebook.read(`Wiki/${path}.md`).catch(() => null);
	if (page) {
		return { kind: 'page' as const, path, title: path.split('/').pop() ?? path, body: page.body };
	}
	const dir = await api.notebook.list(`Wiki/${path}`).catch(() => null);
	if (dir) {
		return { kind: 'directory' as const, path, title: path.split('/').pop() ?? path, entries: dir.entries };
	}
	return { kind: 'not-found' as const, path, title: path };
};
