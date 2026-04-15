import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';
import { adaptThread, adaptThreadDetail } from '$lib/api/adapters';
import { makeRenameThread, makeThreadList } from '$lib/mocks';

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
		console.warn('/api/threads unavailable — trying mocks', err);
		// Fallback: if the requested id matches the rich mock thread, serve it
		// fully populated so the detail surface still exercises real code paths
		// (composer, conversation, variant dispatch) during dev + e2e.
		const rename = makeRenameThread();
		const threads = [rename, ...makeThreadList()];
		// makeRenameThread is the only mock with a full ThreadDetail (messages).
		// For any other id we fall through to the list-only view.
		return {
			threads,
			active: params.id === rename.id ? rename : null,
			apiError: String(err)
		};
	}
};
