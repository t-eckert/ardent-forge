/**
 * Fuzzy matcher stub.
 *
 * In Phase 3, the ⌘K palette uses Bits UI's `Command` primitive, which ships its own
 * battle-tested fuzzy filter. This module exists for one-off cases outside the palette
 * (filtering pinned items, thread rows, etc.) and falls back to a simple substring match.
 */

export function fuzzyMatch(query: string, target: string): boolean {
	if (!query) return true;
	const q = query.toLowerCase();
	const t = target.toLowerCase();
	let i = 0;
	for (const char of t) {
		if (char === q[i]) i++;
		if (i === q.length) return true;
	}
	return false;
}

export function fuzzyFilter<T>(items: T[], query: string, selector: (item: T) => string): T[] {
	if (!query) return items;
	return items.filter((item) => fuzzyMatch(query, selector(item)));
}
