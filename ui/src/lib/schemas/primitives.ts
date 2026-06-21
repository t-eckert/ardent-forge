import { z } from 'zod';

/**
 * Shared primitive schemas.
 *
 * These are the building blocks every higher-level schema (thread, agent, widget payload)
 * composes from. Keeping them here ensures ID formats, date formats, and money shapes stay
 * consistent across the whole system — and stay in sync with what the Python backend emits.
 *
 * Convention: schemas are the source of truth. TypeScript types are always
 * `z.infer<typeof X>` — never hand-written.
 */

/** ISO-8601 timestamp, e.g. "2026-04-12T09:22:18Z" or "2026-04-12T09:22:18+00:00".
 *  Offsets are allowed because the Python backend emits `datetime.isoformat()`,
 *  which produces a `+00:00` offset rather than a `Z` suffix. */
export const IsoDate = z.iso.datetime({ offset: true });
export type IsoDate = z.infer<typeof IsoDate>;

/** ISO-8601 duration, e.g. "PT24M12S". Widget meta often just uses pretty strings,
 *  but durations that feed into logic should use this. */
export const IsoDuration = z.string().regex(/^P(?:\d+Y)?(?:\d+M)?(?:\d+D)?(?:T(?:\d+H)?(?:\d+M)?(?:\d+S)?)?$/);
export type IsoDuration = z.infer<typeof IsoDuration>;

/** Opaque backend-generated identifier */
export const Id = z.string().min(1);
export type Id = z.infer<typeof Id>;

/** URL-safe kebab-case slug */
export const Slug = z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
export type Slug = z.infer<typeof Slug>;

/** Money — stored as string to preserve precision; formatted at display time */
export const Money = z.object({
	amount: z.string(),
	currency: z.string().length(3)
});
export type Money = z.infer<typeof Money>;

/** URL that must parse */
export const Url = z.url();
export type Url = z.infer<typeof Url>;

/** Source system a piece of data came from */
export const Source = z.enum([
	'notebook',
	'garmin',
	'linear',
	'github',
	'calendar',
	'plaid',
	'osm',
	'uptime',
	'astro',
	'manual'
]);
export type Source = z.infer<typeof Source>;

/** Status colour tone used across chips, dots, breadcrumb indicators */
export const Tone = z.enum(['ember', 'moss', 'warn', 'signal', 'graphite', 'stone', 'ink']);
export type Tone = z.infer<typeof Tone>;
