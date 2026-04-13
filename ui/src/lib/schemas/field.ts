import { z } from 'zod';
import { Slug, Source } from './primitives';

/** A Field is a life area within the Library — Health, Redpanda, Art, Ottawa, etc. */
export const Field = z.object({
	slug: Slug,
	/** Display name — "Health", "Redpanda" */
	name: z.string(),
	/** Life-area sub-label — "life area", "work", "practice", "place", "ops" */
	category: z.string(),
	tagline: z.string(),
	/** Short status phrase + tone — "● active", "● 2 PRs", "● quiet" */
	status: z.object({
		label: z.string(),
		tone: z.enum(['ember', 'moss', 'graphite', 'warn'])
	}),
	sources: z.array(Source).min(1),
	/** A small set of named stats shown on the field card */
	stats: z.array(z.object({ label: z.string(), value: z.string() })).max(4),
	/** Whether this field gets the ember-tinted "active field" treatment on the card */
	featured: z.boolean().default(false)
});
export type Field = z.infer<typeof Field>;
