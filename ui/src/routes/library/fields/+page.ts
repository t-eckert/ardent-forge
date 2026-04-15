import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';
import { makeFields } from '$lib/mocks';
import type { Field } from '$lib/schemas/field';

export const ssr = false;

export const load: PageLoad = async () => {
	const mocks = makeFields();
	try {
		const real = await api.fields.list();
		const bySlug = new Map(real.map((r) => [r.slug, r] as const));

		// Build Field objects: prefer API metadata when available, fall back to mock.
		const fields: Field[] = mocks.map((mock) => {
			const hit = bySlug.get(mock.slug);
			if (!hit) return mock;
			return {
				...mock,
				...(hit.category ? { category: hit.category } : {}),
				...(hit.tagline ? { tagline: hit.tagline } : {}),
				...(hit.status ? { status: hit.status } : {}),
				...(hit.sources ? { sources: hit.sources as Field['sources'] } : {}),
				...(hit.featured !== undefined ? { featured: hit.featured } : {}),
				stats: mock.stats.map((s) =>
					s.label.toLowerCase() === 'entries' ? { ...s, value: String(hit.entries) } : s
				)
			};
		});

		// Add any fields from the API that aren't in mocks.
		for (const r of real) {
			if (!mocks.some((m) => m.slug === r.slug)) {
				fields.push({
					slug: r.slug,
					name: r.name,
					category: r.category ?? 'field',
					tagline: r.tagline ?? '',
					status: r.status ?? { label: '● active', tone: 'graphite' },
					sources: (r.sources ?? ['notebook']) as Field['sources'],
					stats: [{ label: 'ENTRIES', value: String(r.entries) }],
					featured: r.featured ?? false
				});
			}
		}

		return { fields };
	} catch (err) {
		console.warn('/api/fields unavailable — using mocks', err);
		return { fields: mocks, apiError: String(err) };
	}
};
