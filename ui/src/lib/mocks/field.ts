import { Field, type Field as FieldT } from '$lib/schemas/field';

export function makeField(overrides: Partial<FieldT> = {}): FieldT {
	return Field.parse({
		slug: 'health',
		name: 'Health',
		category: 'life area',
		tagline: 'Workouts, runs, strength, mobility, readiness. Half-marathon block wk 8/14.',
		status: { label: '● active', tone: 'moss' },
		sources: ['strava', 'notebook'],
		stats: [
			{ label: 'ENTRIES', value: '38' },
			{ label: 'THIS WK', value: '6' },
			{ label: 'SOURCES', value: 'strava · notebook' }
		],
		featured: true,
		...overrides
	});
}

export function makeFields(): FieldT[] {
	return [
		makeField(),
		makeField({
			slug: 'redpanda',
			name: 'Redpanda',
			category: 'work',
			tagline: 'CloudV2 monorepo work. Coordinator, gatekeeper, terraform modules.',
			status: { label: '● 2 PRs', tone: 'ember' },
			sources: ['github', 'linear', 'notebook'],
			stats: [
				{ label: 'ENTRIES', value: '214' },
				{ label: 'OPEN PRS', value: '4' },
				{ label: 'SOURCES', value: 'github · linear · notebook' }
			],
			featured: false
		}),
		makeField({
			slug: 'art',
			name: 'Art',
			category: 'practice',
			tagline: 'Watercolour, drawing, and the slow practice of seeing.',
			status: { label: '● WIP', tone: 'moss' },
			sources: ['notebook'],
			stats: [
				{ label: 'PIECES', value: '38' },
				{ label: 'THIS YR', value: '9' },
				{ label: 'SOURCES', value: 'notebook' }
			],
			featured: false
		}),
		makeField({
			slug: 'ottawa',
			name: 'Ottawa',
			category: 'place',
			tagline: 'Restaurants, routes, city infrastructure notes, seasonal rhythm.',
			status: { label: '● living', tone: 'graphite' },
			sources: ['osm', 'notebook'],
			stats: [
				{ label: 'ENTRIES', value: '76' },
				{ label: 'PLACES', value: '48' },
				{ label: 'SOURCES', value: 'osm · notebook' }
			],
			featured: false
		}),
		makeField({
			slug: 'writing',
			name: 'Writing',
			category: 'practice',
			tagline: 'Field Theories essays, fragments, and drafts in motion.',
			status: { label: '● quiet', tone: 'graphite' },
			sources: ['notebook', 'astro'],
			stats: [
				{ label: 'DRAFTS', value: '12' },
				{ label: 'PUBLISHED', value: '24' },
				{ label: 'SOURCES', value: 'notebook · astro' }
			],
			featured: false
		}),
		makeField({
			slug: 'finances',
			name: 'Finances',
			category: 'ops',
			tagline: 'Budget, accounts, subscriptions, and the quiet math of a year.',
			status: { label: '● monthly close', tone: 'graphite' },
			sources: ['plaid', 'notebook'],
			stats: [
				{ label: 'WK SPEND', value: '$412' },
				{ label: 'ACCOUNTS', value: '6' },
				{ label: 'SOURCES', value: 'plaid · notebook' }
			],
			featured: false
		}),
		makeField({
			slug: 'home',
			name: 'Home',
			category: 'ops',
			tagline: "Homelab, services, DIY projects, Winona's schedule.",
			status: { label: '● living', tone: 'graphite' },
			sources: ['uptime', 'notebook'],
			stats: [
				{ label: 'SERVICES', value: '14' },
				{ label: 'UP', value: '12/14' },
				{ label: 'SOURCES', value: 'uptime · notebook' }
			],
			featured: false
		})
	];
}
