import type { PaletteResult } from '../types';

/** Seed index used by the palette story and the default store until the real index lands. */
export const MOCK_RESULTS: PaletteResult[] = [
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
        id: 'task-rename',
        label: 'Rename tClient → temporalClient',
        breadcrumb: 'Tasks',
        href: '/tasks/01KP000000000000000000CODE',
        class: 'task',
        hint: 'code · executing'
    },
    {
        id: 'action-open-shell',
        label: 'Open Zellij session',
        breadcrumb: 'Action · attaches to agent session',
        class: 'action',
        keywords: ['zellij', 'session', 'attach', 'terminal']
    }
];
