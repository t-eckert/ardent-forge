import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';
import { makeFields } from '$lib/mocks';

export const ssr = false;

export const load: PageLoad = async ({ params }) => {
	const { slug } = params;

	// Try real API first, fall back to mock for display metadata.
	const [fieldSummary, entriesResult] = await Promise.all([
		api.fields.get(slug).catch(() => null),
		api.fields.entries(slug).catch(() => null)
	]);

	// Build a Field object — prefer API data, fill gaps from mock.
	const mocks = makeFields();
	const mockField = mocks.find((f) => f.slug === slug);

	const field = mockField
		? {
				...mockField,
				...(fieldSummary?.category ? { category: fieldSummary.category } : {}),
				...(fieldSummary?.tagline ? { tagline: fieldSummary.tagline } : {}),
				...(fieldSummary?.status ? { status: fieldSummary.status } : {}),
				...(fieldSummary?.sources ? { sources: fieldSummary.sources } : {}),
				stats: mockField.stats.map((s) =>
					s.label.toLowerCase() === 'entries' && fieldSummary
						? { ...s, value: String(fieldSummary.entries) }
						: s
				)
			}
		: fieldSummary
			? {
					slug: fieldSummary.slug,
					name: fieldSummary.name,
					category: fieldSummary.category ?? 'field',
					tagline: fieldSummary.tagline ?? '',
					status: fieldSummary.status ?? { label: '● active', tone: 'graphite' as const },
					sources: (fieldSummary.sources ?? ['notebook']) as Array<
						| 'strava'
						| 'notebook'
						| 'garmin'
						| 'linear'
						| 'github'
						| 'calendar'
						| 'plaid'
						| 'osm'
						| 'uptime'
						| 'astro'
						| 'manual'
					>,
					stats: [{ label: 'ENTRIES', value: String(fieldSummary.entries) }],
					featured: fieldSummary.featured ?? false
				}
			: null;

	return {
		field,
		entries: entriesResult?.entries ?? []
	};
};
