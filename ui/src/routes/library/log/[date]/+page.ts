import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;

export const load: PageLoad = async ({ params }) => {
	const result = await api.notebook.read(`Log/${params.date}.md`).catch(() => null);
	return { date: params.date, body: result?.body ?? null };
};
