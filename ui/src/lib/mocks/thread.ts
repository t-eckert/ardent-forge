import { Thread, ThreadDetail, type Thread as ThreadT, type ThreadDetail as ThreadDetailT } from '$lib/schemas/thread';
import { makeCodeDiff } from './widgets/code-diff';

export function makeThread(overrides: Partial<ThreadT> = {}): ThreadT {
	return Thread.parse({
		id: 'thread-morning',
		title: 'Morning briefing',
		preview: 'weather · repos · code tasks',
		kind: 'code+tools',
		lastActivityIso: hoursAgoIso(3),
		unread: true,
		widgetCount: 3,
		...overrides
	});
}

export function makeThreadList(): ThreadT[] {
	return [
		makeThread(),
		makeThread({
			id: 'thread-forge',
			title: 'Ardent Forge planning',
			preview: 'today: revisit IA + chrome',
			kind: 'code+tools',
			lastActivityIso: hoursAgoIso(26),
			unread: true,
			widgetCount: 0
		}),
		makeThread({
			id: 'thread-pizza',
			title: 'Pizza near home',
			preview: '4 pins · Pizza Pie top pick',
			kind: 'chat',
			lastActivityIso: daysAgoIso(2),
			unread: false,
			widgetCount: 1
		})
	];
}

function hoursAgoIso(h: number): string {
	return new Date(Date.now() - h * 3_600_000).toISOString();
}
function daysAgoIso(d: number): string {
	return new Date(Date.now() - d * 86_400_000).toISOString();
}

/** A full thread detail seeded with the code.diff conversation from the Chat Widgets artboard. */
export function makeRenameThread(): ThreadDetailT {
	const base = makeThread({
		id: 'thread-rename-t-client',
		title: 'Rename tClient → temporalClient',
		preview: 'Found tClient in 4 files. Dry-run diff attached.',
		kind: 'code+tools',
		lastActivityIso: minutesAgoIso(12),
		unread: false,
		widgetCount: 1
	});
	return ThreadDetail.parse({
		...base,
		messages: [
			{
				role: 'user',
				id: 'msg-1',
				iso: minutesAgoIso(28),
				content: 'Rename tClient to temporalClient across the coordinator package.'
			},
			// Turn 1: synchronous widget — Forge shows what it found.
			{
				role: 'assistant',
				id: 'msg-2',
				iso: minutesAgoIso(27),
				toolProfile: 'CODE+TOOLS',
				variant: 'widget',
				text: 'Found tClient in 4 files — 14 occurrences. No callers outside the coordinator package, so this is a clean change. Dispatching code-agent now.',
				widgets: [makeCodeDiff()]
			},
			// Turn 2: task dispatch — live card tracks progress.
			{
				role: 'assistant',
				id: 'msg-3',
				iso: minutesAgoIso(26),
				toolProfile: 'CODE+TOOLS',
				variant: 'task-dispatched',
				text: "I've queued the rename with code-agent. I'll surface the PR here when it's done.",
				dispatchedTask: {
					id: 'run-20260414-rename',
					agent: 'code-agent',
					agentTaskType: 'code',
					title: 'Rename tClient → temporalClient',
					stages: ['triage', 'execute', 'verify', 'deliver'],
					currentStage: 'verify',
					status: 'running',
					startedIso: minutesAgoIso(26)
				}
			},
			// Turn 3: task resolved — narration + artifact embed.
			{
				role: 'assistant',
				id: 'msg-4',
				iso: minutesAgoIso(2),
				toolProfile: 'CODE+TOOLS',
				variant: 'task-resolved',
				text: 'code-agent finished — 4 files, +14/−14, tests green. PR ready for review.',
				resolvedTask: {
					id: 'run-20260414-rename',
					agent: 'code-agent',
					title: 'Rename tClient → temporalClient',
					summary: 'PR #247 opened · 4 files changed · 142/142 tests pass',
					artifact: makeCodeDiff()
				}
			},
			// Turn 4: memory-saved chip — quiet acknowledgement.
			{
				role: 'assistant',
				id: 'msg-5',
				iso: minutesAgoIso(1),
				toolProfile: 'CODE+TOOLS',
				variant: 'memory-saved',
				text: "I'll remember that you prefer package-scoped renames when the identifier isn't exported.",
				savedMemory: {
					name: 'Package-scoped renames',
					description: "Prefer renames that stay inside the package when the identifier isn't exported",
					type: 'feedback'
				}
			}
		]
	});
}

function minutesAgoIso(m: number): string {
	return new Date(Date.now() - m * 60_000).toISOString();
}
