import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';
import { makeFields } from '$lib/mocks';

export const ssr = false;

export const load: PageLoad = async () => {
	const mocks = makeFields();
	try {
		const real = await api.fields.list();
		const byName = new Map(real.map((r) => [r.slug, r] as const));
		// Enrich the mock cards with real entry counts where slugs match.
		// Field cards carry richer display metadata than the backend summary
		// exposes; a later iteration can move that metadata server-side.
		const fields = mocks.map((f) => {
			const hit = byName.get(f.slug);
			if (!hit) return f;
			return {
				...f,
				stats: f.stats.map((s) =>
					s.label.toLowerCase() === 'entries' ? { ...s, value: String(hit.entries) } : s
				)
			};
		});
		return { fields };
	} catch (err) {
		console.warn('/api/fields unavailable — using mocks', err);
		return { fields: mocks, apiError: String(err) };
	}
};
