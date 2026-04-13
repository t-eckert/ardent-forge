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
