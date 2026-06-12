import {
	AgentRun,
	AgentRunDetail,
	type AgentRun as AgentRunT,
	type AgentRunDetail as AgentRunDetailT
} from '$lib/schemas/agent';

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

/** Full list of agents for the list pane on artboard 360-0 */
export function makeAgentRunList(): AgentRunT[] {
	return [
		makeAgentRun(),
		makeAgentRun({
			id: 'run-20260413-0502',
			kind: 'triage-agent',
			startedIso: hoursAgoIso(4.8),
			durationLabel: '7m',
			status: 'done',
			summary: '8 Linear issues labelled'
		}),
		makeAgentRun({
			id: 'run-20260413-0600',
			kind: 'notebook-sync',
			startedIso: hoursAgoIso(3.8),
			durationLabel: '1m',
			status: 'done',
			summary: '14 logs · 3 new wiki links'
		}),
		makeAgentRun({
			id: 'run-ci-idle',
			kind: 'ci-watcher',
			startedIso: hoursAgoIso(12),
			durationLabel: 'github webhook · idle',
			status: 'watching',
			summary: 'cloudv2 · all green'
		}),
		makeAgentRun({
			id: 'run-20260413-0200',
			kind: 'backup-agent',
			startedIso: hoursAgoIso(9.6),
			durationLabel: 'auth err',
			status: 'failed',
			summary: 'B2 token expired · retry queued'
		})
	];
}

/** Full detail for the code-agent run, matching artboard 360-0 */
export function makeCodeAgentRunDetail(): AgentRunDetailT {
	const startIso = hoursAgoIso(7.5);
	return AgentRunDetail.parse({
		...makeAgentRun(),
		triggerNote: 'scheduled 02:00',
		title: 'Rename tClient → temporalClient in coordinator',
		queuedBy: 'Thomas',
		runtime: 'code-agent@0.4.2',
		metas: [
			{ label: 'STATUS', value: 'needs review', tone: 'ember' },
			{ label: 'DURATION', value: '24m 12s' },
			{ label: 'TOKENS', value: '42,118' },
			{ label: 'COST', value: '$0.84' },
			{ label: 'TOOL CALLS', value: '18' },
			{ label: 'TESTS', value: '142 / 142 ✓', tone: 'moss' }
		],
		steps: [
			{ id: 'step-1', atIso: startIso, summary: 'Clone cloudv2 · checkout main', meta: 'git.clone · 42s', state: 'done' },
			{ id: 'step-2', atIso: startIso, summary: 'Locate tClient occurrences · 14 hits in 4 files', meta: 'rg · 1.2s', state: 'done' },
			{ id: 'step-3', atIso: startIso, summary: 'Verify no external callers · package-scoped', meta: 'gopls · 14s', state: 'done' },
			{ id: 'step-4', atIso: startIso, summary: 'Apply rename across coordinator.go, tick.go, watcher.go, coordinator_test.go', meta: 'edit · 4 files · 14 lines', state: 'done' },
			{ id: 'step-5', atIso: startIso, summary: 'Run ./taskw fmt && ./taskw lint', meta: 'shell · 1m 48s · clean', state: 'done' },
			{ id: 'step-6', atIso: startIso, summary: 'Run ./taskw test:unit · 142 pass', meta: 'shell · 19m 04s', state: 'done' },
			{ id: 'step-7', atIso: startIso, summary: 'Push branch rename/t-client · open PR #247', meta: 'gh · 6s', state: 'done' },
			{ id: 'step-8', atIso: startIso, summary: 'Await human review · notified Today briefing', meta: 'blocked · waiting on Thomas', state: 'waiting' }
		],
		artifactLabel: 'PR #247'
	});
}
