import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;

export const load: PageLoad = async ({ params }) => {
	const result = await api.notebook.read(`People/${params.name}.md`).catch(() => null);
	return { name: params.name, body: result?.body ?? null };
};
