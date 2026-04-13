import { AgentRun, type AgentRun as AgentRunT } from '$lib/schemas/agent';

export function makeAgentRun(overrides: Partial<AgentRunT> = {}): AgentRunT {
	return AgentRun.parse({
		id: 'run-20260413-0214',
		kind: 'code-agent',
		startedIso: hoursAgoIso(7.5),
		durationLabel: '24m',
		status: 'needs-review',
		summary: 'PR open: rename/t-client — 4 files, +14/−14, tests green.',
		href: '/agents/code-agent/run-20260413-0214',
		...overrides
	});
}

export function makeOvernightRuns(): AgentRunT[] {
	return [
		makeAgentRun(),
		makeAgentRun({
			id: 'run-20260413-0502',
			kind: 'triage-agent',
			startedIso: hoursAgoIso(4.8),
			durationLabel: '7m',
			status: 'done',
			summary: 'Labelled 8 Linear issues · 2 flagged devagent.',
			href: '/agents/triage-agent/run-20260413-0502'
		}),
		makeAgentRun({
			id: 'run-20260413-0600',
			kind: 'notebook-sync',
			startedIso: hoursAgoIso(3.8),
			durationLabel: '1m',
			status: 'done',
			summary: 'Pulled 14 daily logs from Obsidian vault. 3 new wiki links.',
			href: '/agents/notebook-sync/run-20260413-0600'
		})
	];
}

function hoursAgoIso(h: number): string {
	return new Date(Date.now() - h * 3_600_000).toISOString();
}
