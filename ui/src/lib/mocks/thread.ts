import { Thread, type Thread as ThreadT } from '$lib/schemas/thread';

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
