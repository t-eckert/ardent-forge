/**
 * Derive chrome state from the current URL.
 *
 * The sidebar active spine and the breadcrumb strip both read from here so they
 * stay in lockstep with navigation. Feed `path` from `$page.url.pathname` at
 * layout level.
 */

export type Spine = 'today' | 'repos' | 'tasks' | 'agents' | 'connectors' | 'schedules' | 'memory' | 'log';

export interface BreadcrumbSegment {
	label: string;
	href?: string;
}

const spineFromPath = (path: string): Spine | null => {
	if (path.startsWith('/today')) return 'today';
	if (path.startsWith('/repos')) return 'repos';
	if (path.startsWith('/tasks')) return 'tasks';
	if (path.startsWith('/library/agents')) return 'agents';
	if (path.startsWith('/library/connectors')) return 'connectors';
	if (path.startsWith('/library/schedules')) return 'schedules';
	if (path.startsWith('/library/memory')) return 'memory';
	if (path.startsWith('/library/log')) return 'log';
	return null;
};

/** Build a breadcrumb trail from a pathname. Produces an empty array for top-level
 *  spine surfaces — per the chrome spec, top-level pages don't render a strip. */
export function breadcrumbForPath(path: string): BreadcrumbSegment[] {
	const segments = path.split('/').filter(Boolean);
	if (segments.length <= 1) return [];

	const trail: BreadcrumbSegment[] = [];
	let href = '';
	for (let i = 0; i < segments.length; i++) {
		href += '/' + segments[i];
		trail.push({
			label: humanise(segments[i]),
			href: i === segments.length - 1 ? undefined : href
		});
	}
	return trail;
}

function humanise(segment: string): string {
	// Handle route param placeholders and slugs
	if (segment.startsWith('[') && segment.endsWith(']')) return segment.slice(1, -1);
	return segment
		.split('-')
		.map((w) => w.charAt(0).toUpperCase() + w.slice(1))
		.join(' ');
}

export const chromeState = {
	spineFor(path: string): Spine | null {
		return spineFromPath(path);
	},
	breadcrumbFor(path: string): BreadcrumbSegment[] {
		return breadcrumbForPath(path);
	}
};
