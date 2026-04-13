import { Thread, ThreadDetail, type Thread as ThreadT, type ThreadDetail as ThreadDetailT } from '$lib/schemas/thread';
import { makeCodeDiff } from './widgets/code-diff';

export function makeThread(overrides: Partial<ThreadT> = {}): ThreadT {
	return Thread.parse({
		id: 'thread-morning',
		title: 'Morning briefing',
		preview: 'weather · purchases · long run fuel',
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
			kind: 'places+tools',
			lastActivityIso: daysAgoIso(2),
			unread: false,
			widgetCount: 1
		}),
		makeThread({
			id: 'thread-purchases',
			title: 'Weekly purchases review',
			preview: '$412.86 · groceries leading',
			kind: 'code+tools',
			lastActivityIso: daysAgoIso(6),
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
				iso: minutesAgoIso(14),
				content: 'Rename tClient to temporalClient across the coordinator package.'
			},
			{
				role: 'assistant',
				id: 'msg-2',
				iso: minutesAgoIso(12),
				toolProfile: 'CODE+TOOLS',
				text: 'Found tClient in 4 files — 14 occurrences. Proposed rename below; no callers outside the coordinator package, so this is a clean change.',
				widgets: [makeCodeDiff()]
			}
		]
	});
}

function minutesAgoIso(m: number): string {
	return new Date(Date.now() - m * 60_000).toISOString();
}
