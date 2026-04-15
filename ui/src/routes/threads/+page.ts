import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';
import { adaptThread } from '$lib/api/adapters';
import { makeThreadList, makeRenameThread } from '$lib/mocks';

export const ssr = false;

export const load: PageLoad = async () => {
	try {
		const raw = await api.threads.list();
		return { threads: raw.map((t) => adaptThread(t)) };
	} catch (err) {
		console.warn('/api/threads unavailable — using mocks', err);
		return {
			threads: [makeRenameThread(), ...makeThreadList()],
			apiError: String(err)
		};
	}
};
