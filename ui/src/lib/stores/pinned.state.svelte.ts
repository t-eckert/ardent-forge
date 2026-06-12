/**
 * User-curated pinned shortcuts shown in the sidebar.
 *
 * Replaces the ad-hoc top-level nav items (Dashboard/Health/Schedule) from the old IA.
 * If you want something one click away, pin it.
 */

export interface PinnedItem {
	id: string;
	label: string;
	href: string;
	/** kind affects the glyph used by the sidebar row */
	kind: 'thread' | 'note' | 'agent';
}

const DEFAULTS: PinnedItem[] = [
	{ id: 'todays-log', label: "Today's log", href: '/library/log/today', kind: 'note' }
];

const items = $state<PinnedItem[]>(DEFAULTS);

export const pinned = {
	get items() {
		return items;
	},
	add(item: PinnedItem) {
		if (!items.some((i) => i.id === item.id)) items.push(item);
	},
	remove(id: string) {
		const i = items.findIndex((item) => item.id === id);
		if (i !== -1) items.splice(i, 1);
	},
	isPinned(id: string) {
		return items.some((i) => i.id === id);
	}
};
