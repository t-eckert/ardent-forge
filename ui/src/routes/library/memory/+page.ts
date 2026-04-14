import type { PageLoad } from './$types';
import { api, type MemoryEntry } from '$lib/api/typed';

// SPA mode — all fetches happen in the browser. Mock fallback if the API
// is unreachable keeps Storybook + offline dev working without changes.
export const ssr = false;

const FALLBACK: MemoryEntry[] = [
	{
		filename: 'user_role.md',
		slug: 'user_role',
		name: 'User role',
		description: 'Software engineer at Redpanda, currently building Ardent Forge',
		type: 'user',
		body: 'Focus on async Python + TypeScript + NixOS.',
		updated_at: '2026-04-13'
	},
	{
		filename: 'numbers_mono.md',
		slug: 'numbers_mono',
		name: 'Numbers always mono',
		description: 'All numeric values render in JetBrains Mono; Playfair is for words only',
		type: 'feedback',
		body: 'Enforced via the <Stat> component.',
		updated_at: '2026-04-12'
	}
];

export const load: PageLoad = async () => {
	try {
		return { entries: await api.memory.list() };
	} catch (err) {
		console.warn('/api/memory unavailable — using fallback', err);
		return { entries: FALLBACK, apiError: String(err) };
	}
};
