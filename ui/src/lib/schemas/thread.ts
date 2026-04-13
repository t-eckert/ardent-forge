import { z } from 'zod';
import { Id, IsoDate } from './primitives';
import { WidgetPayload } from './widgets';

/** A conversation between the user and the Forge — the unit shown in the Threads surface. */
export const Thread = z.object({
	id: Id,
	title: z.string(),
	/** One-line summary for preview rows */
	preview: z.string(),
	/** Tool capabilities exposed in this thread (shown as a chip) */
	kind: z.enum(['code+tools', 'health+tools', 'places+tools', 'chat']),
	lastActivityIso: IsoDate,
	unread: z.boolean().default(false),
	/** Widget count — shown as "3 widgets" chip when > 0 */
	widgetCount: z.number().int().nonnegative().default(0)
});
export type Thread = z.infer<typeof Thread>;

/** A single message in a thread — either from the user or from the Forge assistant. */
export const UserMessage = z.object({
	role: z.literal('user'),
	id: Id,
	iso: IsoDate,
	content: z.string()
});
export const AssistantMessage = z.object({
	role: z.literal('assistant'),
	id: Id,
	iso: IsoDate,
	/** Tool profile label shown in the header, e.g. "CODE+TOOLS" */
	toolProfile: z.string(),
	/** Prose paragraph rendered above any widgets */
	text: z.string().optional(),
	/** Embedded widgets rendered via WidgetHost */
	widgets: z.array(WidgetPayload).default([])
});
export const Message = z.discriminatedUnion('role', [UserMessage, AssistantMessage]);
export type UserMessage = z.infer<typeof UserMessage>;
export type AssistantMessage = z.infer<typeof AssistantMessage>;
export type Message = z.infer<typeof Message>;

/** A full thread detail — metadata + ordered messages. */
export const ThreadDetail = Thread.extend({
	messages: z.array(Message)
});
export type ThreadDetail = z.infer<typeof ThreadDetail>;
