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
	kind: z.enum(['code+tools', 'chat']),
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
export type UserMessage = z.infer<typeof UserMessage>;

/** Five assistant message shapes. Every shape renders under one Forge avatar; the
 *  variant discriminator drives which sub-component in threads/components renders. */
export const MessageVariant = z.enum([
	'text',
	'widget',
	'task-dispatched',
	'task-resolved',
	'memory-saved'
]);
export type MessageVariant = z.infer<typeof MessageVariant>;

/** Live-updating card shown when Forge dispatches a task mid-turn. */
export const DispatchedTask = z.object({
	id: Id,
	agent: z.string(),
	agentTaskType: z.string(),
	title: z.string(),
	stages: z.array(z.string()),
	/** Which stage is currently active — used by the live indicator */
	currentStage: z.string().optional(),
	status: z.enum(['queued', 'running', 'needs-review', 'done', 'failed']),
	startedIso: IsoDate
});
export type DispatchedTask = z.infer<typeof DispatchedTask>;

/** Summary of a completed task whose resolution is being narrated. */
export const ResolvedTask = z.object({
	id: Id,
	agent: z.string(),
	title: z.string(),
	summary: z.string(),
	/** The artifact widget Forge embeds alongside the narration. */
	artifact: WidgetPayload.optional()
});
export type ResolvedTask = z.infer<typeof ResolvedTask>;

/** Inline chip surfaced when Forge writes a memory mid-conversation. */
export const SavedMemory = z.object({
	name: z.string(),
	description: z.string(),
	type: z.enum(['user', 'feedback', 'project', 'reference'])
});
export type SavedMemory = z.infer<typeof SavedMemory>;

export const AssistantMessage = z.object({
	role: z.literal('assistant'),
	id: Id,
	iso: IsoDate,
	/** Tool profile label shown in the header, e.g. "CODE+TOOLS" */
	toolProfile: z.string(),
	variant: MessageVariant.default('text'),
	/** Prose paragraph rendered above any widgets / cards / chips */
	text: z.string().optional(),
	/** variant === 'widget': embedded tool results */
	widgets: z.array(WidgetPayload).default([]),
	/** variant === 'task-dispatched': the live card payload */
	dispatchedTask: DispatchedTask.optional(),
	/** variant === 'task-resolved': narration target + artifact */
	resolvedTask: ResolvedTask.optional(),
	/** variant === 'memory-saved': the inline chip */
	savedMemory: SavedMemory.optional()
});
export type AssistantMessage = z.infer<typeof AssistantMessage>;

export const Message = z.discriminatedUnion('role', [UserMessage, AssistantMessage]);
export type Message = z.infer<typeof Message>;

/** A full thread detail — metadata + ordered messages. */
export const ThreadDetail = Thread.extend({
	messages: z.array(Message)
});
export type ThreadDetail = z.infer<typeof ThreadDetail>;
