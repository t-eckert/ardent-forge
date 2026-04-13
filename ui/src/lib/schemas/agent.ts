import { z } from 'zod';
import { Id, IsoDate } from './primitives';

export const AgentKind = z.enum([
	'code-agent',
	'triage-agent',
	'notebook-sync',
	'strava-pull',
	'ci-watcher',
	'backup-agent'
]);
export type AgentKind = z.infer<typeof AgentKind>;

export const RunStatus = z.enum(['running', 'needs-review', 'done', 'failed', 'cron', 'watching']);
export type RunStatus = z.infer<typeof RunStatus>;

export const AgentRun = z.object({
	id: Id,
	kind: AgentKind,
	startedIso: IsoDate,
	/** ISO duration or "live" if still running */
	durationLabel: z.string(),
	status: RunStatus,
	summary: z.string(),
	/** Optional link target when user clicks through */
	href: z.string().optional()
});
export type AgentRun = z.infer<typeof AgentRun>;

/** A single step in a run's timeline — shown in the run detail view. */
export const RunStep = z.object({
	id: Id,
	/** ISO timestamp when the step started */
	atIso: IsoDate,
	/** One-line description of what happened */
	summary: z.string(),
	/** Tool/call + duration, e.g. "rg · 1.2s" */
	meta: z.string(),
	/** Step outcome: ✓ green, ? yellow (awaiting), ✗ red */
	state: z.enum(['done', 'waiting', 'failed'])
});
export type RunStep = z.infer<typeof RunStep>;

/** Full run detail — trigger, meta strip figures, steps, optional artifact widget id. */
export const AgentRunDetail = AgentRun.extend({
	triggerNote: z.string(),
	title: z.string(),
	/** Who/what queued it */
	queuedBy: z.string(),
	/** Agent @version */
	runtime: z.string(),
	metas: z.array(z.object({ label: z.string(), value: z.string(), tone: z.enum(['default', 'ember', 'moss', 'warn']).optional() })),
	steps: z.array(RunStep),
	/** Optional embedded artifact — for code-agent this is a code.diff payload */
	artifactLabel: z.string().optional()
});
export type AgentRunDetail = z.infer<typeof AgentRunDetail>;
