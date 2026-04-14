import type { PaletteResult } from '../types';

/** Seed index used by the palette story and the default store until the real index lands. */
export const MOCK_RESULTS: PaletteResult[] = [
	{
		id: 'workout-today',
		label: 'Long run · 18 km',
		breadcrumb: 'Health › Workouts › today',
		href: '/library/fields/health/workouts/today',
		class: 'workout',
		hint: 'today · 10:00',
		recentBoost: 10,
		pinned: true,
		keywords: ['today', 'run', 'long']
	},
	{
		id: 'workout-tempo',
		label: 'Tempo 6×1km',
		breadcrumb: 'Health › Workouts › recent',
		href: '/library/fields/health/workouts/tempo-6x1km',
		class: 'workout',
		hint: 'Apr 10 · strava',
		keywords: ['tempo', 'intervals']
	},
	{
		id: 'todo-stretching',
		label: 'Stretching · 15 min',
		breadcrumb: 'Todos › Personal',
		href: '/library/todos/stretching',
		class: 'todo',
		hint: 'due today',
		recentBoost: 5
	},
	{
		id: 'note-today-log',
		label: "Today's log",
		breadcrumb: 'Library › Notebook › Log',
		href: '/library/log/today',
		class: 'note',
		hint: '2026-04-12.md',
		pinned: true
	},
	{
		id: 'note-workout-plan',
		label: 'Workout plan — half-marathon build',
		breadcrumb: 'Library › Fields › Health',
		href: '/library/fields/health/plan',
		class: 'note'
	},
	{
		id: 'thread-morning',
		label: 'Morning briefing',
		breadcrumb: 'Threads',
		href: '/threads/morning-briefing',
		class: 'thread',
		hint: '06:12',
		recentBoost: 8
	},
	{
		id: 'action-start-workout',
		label: 'Start workout · long run',
		breadcrumb: 'Action · records session to Strava + Notebook',
		class: 'action',
		hint: 'health.workouts',
		keywords: ['begin', 'run', 'workout']
	},
	{
		id: 'action-draft-tomorrow',
		label: "Draft tomorrow's workout",
		breadcrumb: 'Action · opens notebook entry',
		class: 'action',
		keywords: ['plan', 'tomorrow']
	}
];
