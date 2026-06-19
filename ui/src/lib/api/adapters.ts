/**
 * Adapters — map backend wire shapes to frontend schema shapes.
 */

import type { Task } from '$lib/schemas/task';
import type { AgentRun } from '$lib/schemas/agent';

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

