/**
 * Global sync status per external source.
 *
 * Drives the sync pip in the sidebar footer and the sync indicator in breadcrumbs.
 * In Storybook mode this is seeded with mock timestamps; in hybrid/deployed mode it
 * gets populated from `GET /api/sources` (to be defined).
 */

import type { Source } from '$lib/schemas';

export type SyncState = 'live' | 'synced' | 'stale' | 'failing' | 'optional';

export interface SourceSync {
	source: Source;
	state: SyncState;
	lastSyncIso?: string;
}

const DEFAULTS: SourceSync[] = [
	{ source: 'notebook', state: 'synced', lastSyncIso: iso(-2) },
	{ source: 'linear', state: 'synced', lastSyncIso: iso(-6) },
	{ source: 'github', state: 'live', lastSyncIso: iso(-1) },
	{ source: 'calendar', state: 'synced', lastSyncIso: iso(-9) },
	{ source: 'garmin', state: 'optional' }
];

function iso(minutesAgo: number): string {
	return new Date(Date.now() + minutesAgo * 60_000).toISOString();
}

const sources = $state<SourceSync[]>(DEFAULTS);

export const sync = {
	get sources() {
		return sources;
	},
	get overall(): SyncState {
		const states = sources.map((s) => s.state);
		if (states.includes('failing')) return 'failing';
		if (states.includes('stale')) return 'stale';
		if (states.some((s) => s === 'live' || s === 'synced')) return 'synced';
		return 'optional';
	},
	get lastSyncIso(): string | undefined {
		return sources
			.filter((s) => s.lastSyncIso)
			.map((s) => s.lastSyncIso!)
			.sort()
			.at(-1);
	},
	set(source: Source, patch: Partial<Omit<SourceSync, 'source'>>) {
		const i = sources.findIndex((s) => s.source === source);
		if (i === -1) {
			sources.push({ source, state: 'synced', ...patch });
		} else {
			sources[i] = { ...sources[i], ...patch };
		}
	}
};
