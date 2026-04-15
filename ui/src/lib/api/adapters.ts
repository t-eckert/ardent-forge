/**
 * Adapters — map backend wire shapes to frontend schema shapes.
 *
 * The backend uses snake_case and has a slightly different thread/message
 * model (no preview text, no widgetCount cached on the thread row). These
 * helpers bridge the gap at the route loader boundary so views only ever
 * see the frontend schema types.
 */

import type { BackendThread, BackendThreadDetail, BackendTaskSummary } from './typed';
import type {
	Thread,
	ThreadDetail,
	Message,
	AssistantMessage,
	UserMessage,
	DispatchedTask,
	ResolvedTask
} from '$lib/schemas/thread';

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

/** Backend task status → frontend DispatchedTask.status. Bucket intermediate
 *  stages under 'running' and the delivery/verify stages under 'needs-review'
 *  so the chip matches what the user cares about. */
function dispatchedStatus(raw: string): DispatchedTask['status'] {
	switch (raw) {
		case 'queued':
			return 'queued';
		case 'triaging':
		case 'executing':
			return 'running';
		case 'verifying':
		case 'delivering':
			return 'needs-review';
		case 'completed':
			return 'done';
		case 'failed':
			return 'failed';
		default:
			return 'running';
	}
}

function adaptDispatched(
	taskId: string,
	iso: string,
	task: BackendTaskSummary
): DispatchedTask {
	return {
		id: taskId,
		agent: `${task.type}-agent`,
		agentTaskType: task.type,
		title: task.title,
		stages: task.stages,
		currentStage: task.current_stage ?? undefined,
		status: dispatchedStatus(task.status),
		startedIso: iso
	};
}

function adaptResolved(
	taskId: string,
	task: BackendTaskSummary,
	narration: string
): ResolvedTask {
	// Wrap the agent's result in the generic ResultWidget when non-empty.
	// Richer per-agent widget shapes (code.diff, places.map, etc.) will be
	// matched first here once they're specced; for now every agent falls
	// through to the generic dump.
	const data = task.result ?? undefined;
	const hasResult = data && typeof data === 'object' && Object.keys(data).length > 0;
	return {
		id: taskId,
		agent: `${task.type}-agent`,
		title: task.title,
		summary: narration,
		artifact: hasResult
			? {
					tool: 'result',
					label: `${task.type} output`,
					data: data as Record<string, unknown>
				}
			: undefined
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

	// Populate the variant-specific nested objects from the backend's embedded
	// task summary when present. If the task was deleted (task == null) we
	// fall back to rendering the stored narration as plain text.
	if (m.task_id && m.task) {
		if (variant === 'task-dispatched') {
			a.dispatchedTask = adaptDispatched(m.task_id, m.created_at, m.task);
		} else if (variant === 'task-resolved') {
			a.resolvedTask = adaptResolved(m.task_id, m.task, m.content);
		}
	}

	return a;
}

export function adaptThreadDetail(t: BackendThreadDetail): ThreadDetail {
	const widgetCount = t.messages.reduce((n, m) => n + (m.widgets?.length ?? 0), 0);
	return {
		...adaptThread(t, widgetCount, t.messages[0]?.content ?? ''),
		messages: t.messages.map(adaptMessage)
	};
}
