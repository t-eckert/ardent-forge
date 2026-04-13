/**
 * Date + time formatters for the Ardent Forge UI.
 *
 * All dates in the system are ISO-8601 strings (UTC). Formatters convert for display.
 * User is in Eastern Time (America/Toronto) per personal context — we default to that
 * unless the app explicitly overrides.
 */

const LOCALE = 'en-CA';
const TZ = 'America/Toronto';

export function formatTime(iso: string): string {
	return new Date(iso).toLocaleTimeString(LOCALE, {
		hour: '2-digit',
		minute: '2-digit',
		hour12: false,
		timeZone: TZ
	});
}

export function formatDateShort(iso: string): string {
	return new Date(iso).toLocaleDateString(LOCALE, {
		month: 'short',
		day: '2-digit',
		timeZone: TZ
	});
}

export function formatDateFull(iso: string): string {
	return new Date(iso).toLocaleDateString(LOCALE, {
		weekday: 'long',
		day: 'numeric',
		month: 'long',
		year: 'numeric',
		timeZone: TZ
	});
}

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
	['year', 60 * 60 * 24 * 365],
	['month', 60 * 60 * 24 * 30],
	['week', 60 * 60 * 24 * 7],
	['day', 60 * 60 * 24],
	['hour', 60 * 60],
	['minute', 60],
	['second', 1]
];

export function formatRelative(iso: string, now: Date = new Date()): string {
	const seconds = (new Date(iso).getTime() - now.getTime()) / 1000;
	const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: 'auto' });
	for (const [unit, secondsInUnit] of UNITS) {
		if (Math.abs(seconds) >= secondsInUnit || unit === 'second') {
			return rtf.format(Math.round(seconds / secondsInUnit), unit);
		}
	}
	return 'just now';
}
