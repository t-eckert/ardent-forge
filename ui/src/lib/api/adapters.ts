/**
 * Adapters — map backend wire shapes to frontend schema shapes.
 *
 * The backend uses snake_case and has a slightly different thread/message
 * model (no preview text, no widgetCount cached on the thread row). These
 * helpers bridge the gap at the route loader boundary so views only ever
 * see the frontend schema types.
 */

import type { BackendThread, BackendThreadDetail } from './typed';
import type { Thread, ThreadDetail, Message, AssistantMessage, UserMessage } from '$lib/schemas/thread';

const KNOWN_KINDS = ['code+tools', 'health+tools', 'places+tools', 'chat'] as const;
type Kind = (typeof KNOWN_KINDS)[number];

function coerceKind(raw: string): Kind {
	return (KNOWN_KINDS as readonly string[]).includes(raw) ? (raw as Kind) : 'chat';
}

export function adaptThread(t: BackendThread, widgetCount = 0, preview = ''): Thread {
	return {
		id: t.id,
		title: t.title,
		preview: preview || t.title,
		kind: coerceKind(t.kind),
		lastActivityIso: t.last_activity_at,
		unread: t.unread,
		widgetCount
	};
}

function adaptMessage(m: BackendThreadDetail['messages'][number]): Message {
	if (m.role === 'user') {
		const u: UserMessage = { role: 'user', id: m.id, iso: m.created_at, content: m.content };
		return u;
	}
	// Backend variant strings map onto frontend MessageVariant; unknown → 'text'.
	const variant = ['text', 'widget', 'task-dispatched', 'task-resolved', 'memory-saved'].includes(
		m.variant
	)
		? (m.variant as AssistantMessage['variant'])
		: 'text';
	const a: AssistantMessage = {
		role: 'assistant',
		id: m.id,
		iso: m.created_at,
		toolProfile: 'FORGE',
		variant,
		text: m.content,
		widgets: []
	};
	return a;
}

export function adaptThreadDetail(t: BackendThreadDetail): ThreadDetail {
	const widgetCount = t.messages.reduce((n, m) => n + (m.widgets?.length ?? 0), 0);
	return {
		...adaptThread(t, widgetCount, t.messages[0]?.content ?? ''),
		messages: t.messages.map(adaptMessage)
	};
}
