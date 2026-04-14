import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';
import type { Task } from '$lib/schemas/task';
import type { AgentRun, AgentKind, RunStatus } from '$lib/schemas/agent';
import { makeAgentRunList } from '$lib/mocks';

export const ssr = false;

const statusMap: Record<string, RunStatus> = {
	queued: 'running',
	triaging: 'running',
	executing: 'running',
	verifying: 'needs-review',
	delivering: 'needs-review',
	completed: 'done',
	failed: 'failed'
};

const kindMap: Record<string, AgentKind> = {
	code: 'code-agent',
	plan: 'triage-agent',
	research: 'triage-agent',
	tickets: 'triage-agent',
	echo: 'triage-agent'
};

function taskToRun(task: Task): AgentRun {
	return {
		id: task.id,
		kind: kindMap[task.type] ?? 'triage-agent',
		startedIso: task.created_at,
		durationLabel: task.completed_at ? 'done' : 'live',
		status: statusMap[task.status] ?? 'running',
		summary: task.title || task.description.slice(0, 80),
		href: `/tasks/${task.id}`
	};
}

export const load: PageLoad = async () => {
	try {
		const tasks = await api.tasks.list();
		return { runs: tasks.map(taskToRun) };
	} catch (err) {
		console.warn('/api/tasks unavailable — using mocks', err);
		return { runs: makeAgentRunList(), apiError: String(err) };
	}
};
