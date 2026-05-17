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
import type { Task } from '$lib/schemas/task';
import type { AgentRun } from '$lib/schemas/agent';

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
	const data = task.result ?? undefined;
	const hasResult = data && typeof data === 'object' && Object.keys(data).length > 0;
	return {
		id: taskId,
		agent: `${task.type}-agent`,
		title: task.title,
		summary: narration,
		artifact: hasResult ? pickArtifact(task.type, data as Record<string, unknown>) : undefined
	};
}

/** Route an agent's result dict to the best-matching widget shape.
 *  Adding a new per-agent widget means adding a branch here. Anything
 *  unrecognised falls through to the generic ResultWidget. */
function pickArtifact(
	taskType: string,
	data: Record<string, unknown>
): NonNullable<ResolvedTask['artifact']> {
	if (taskType === 'code' && ('pr_url' in data || 'branch' in data)) {
		return {
			tool: 'code.result',
			prUrl: typeof data.pr_url === 'string' ? data.pr_url : undefined,
			branch: typeof data.branch === 'string' ? data.branch : undefined,
			summary: typeof data.summary === 'string' ? data.summary : undefined,
			claudeOutput: typeof data.claude_output === 'string' ? data.claude_output : undefined
		};
	}
	return {
		tool: 'result',
		label: `${taskType} output`,
		data
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

/** Map a backend Task into the frontend AgentRun shape used by OvernightDigest
 *  and AgentsRoster. */
export function adaptTaskToAgentRun(task: Task): AgentRun {
	const kind = `${task.type}-agent`;

	let status: AgentRun['status'];
	switch (task.status) {
		case 'completed':
			status = 'done';
			break;
		case 'failed':
			status = 'failed';
			break;
		case 'verifying':
		case 'delivering':
			status = 'needs-review';
			break;
		default:
			status = 'running';
	}

	let durationLabel = '—';
	if (task.completed_at) {
		const start = new Date(task.created_at).getTime();
		const end = new Date(task.completed_at).getTime();
		const mins = Math.round((end - start) / 60000);
		durationLabel = mins < 60 ? `${mins}m` : `${Math.round(mins / 6) / 10}h`;
	} else if (status === 'running') {
		durationLabel = 'live';
	}

	return {
		id: task.id,
		kind,
		startedIso: task.created_at,
		durationLabel,
		status,
		summary: task.title,
		href: `/tasks/${task.id}`
	};
}

export function adaptThreadDetail(t: BackendThreadDetail): ThreadDetail {
	const widgetCount = t.messages.reduce((n, m) => n + (m.widgets?.length ?? 0), 0);
	return {
		...adaptThread(t, widgetCount, t.messages[0]?.content ?? ''),
		messages: t.messages.map(adaptMessage)
	};
}
