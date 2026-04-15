import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';
import { adaptThread, adaptThreadDetail } from '$lib/api/adapters';

export const ssr = false;

export const load: PageLoad = async ({ params }) => {
	try {
		const [rawList, rawDetail] = await Promise.all([
			api.threads.list(),
			api.threads.get(params.id).catch(() => null)
		]);
		return {
			threads: rawList.map((t) => adaptThread(t)),
			active: rawDetail ? adaptThreadDetail(rawDetail) : null
		};
	} catch (err) {
		console.warn('/api/threads unavailable', err);
		return { threads: [], active: null, apiError: String(err) };
	}
};
