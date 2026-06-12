import { describe, it, expect } from 'vitest';
import { adaptThreadDetail } from './adapters';

const baseThread = {
	id: 'thread-1',
	title: 'Research Svelte 5',
	kind: 'code+tools',
	last_activity_at: '2026-04-15T00:00:00Z',
	unread: false,
	created_at: '2026-04-15T00:00:00Z'
};

describe('adaptThreadDetail — task variant enrichment', () => {
	it('maps a task-dispatched backend message into a populated DispatchedTask', () => {
		const detail = adaptThreadDetail({
			...baseThread,
			messages: [
				{
					id: 'msg-1',
					thread_id: baseThread.id,
					role: 'assistant',
					content: 'dispatched code — Svelte 5',
					variant: 'task-dispatched',
					widgets: [],
					task_id: '01KP00000000000000000000AA',
					tool_use_id: 'toolu_1',
					task: {
						id: '01KP00000000000000000000AA',
						type: 'code',
						title: 'Svelte 5 notes',
						status: 'executing',
						stages: ['triage', 'execute', 'verify', 'deliver'],
						current_stage: 'execute',
						result: null,
						completed_at: null
					},
					created_at: '2026-04-15T00:00:01Z'
				}
			]
		});

		const m = detail.messages[0];
		if (m.role !== 'assistant') throw new Error('expected assistant message');
		expect(m.variant).toBe('task-dispatched');
		expect(m.dispatchedTask).toBeDefined();
		expect(m.dispatchedTask!.id).toBe('01KP00000000000000000000AA');
		expect(m.dispatchedTask!.agentTaskType).toBe('code');
		expect(m.dispatchedTask!.agent).toBe('code-agent');
		expect(m.dispatchedTask!.stages).toEqual(['triage', 'execute', 'verify', 'deliver']);
		expect(m.dispatchedTask!.currentStage).toBe('execute');
		expect(m.dispatchedTask!.status).toBe('running');
	});

	it('maps a completed task-resolved message into a ResolvedTask', () => {
		const detail = adaptThreadDetail({
			...baseThread,
			messages: [
				{
					id: 'msg-2',
					thread_id: baseThread.id,
					role: 'assistant',
					content: 'code finished — svelte 5 notes. 1 notes written',
					variant: 'task-resolved',
					widgets: [],
					task_id: '01KP00000000000000000000AA',
					task: {
						id: '01KP00000000000000000000AA',
						type: 'code',
						title: 'Svelte 5 notes',
						status: 'completed',
						stages: ['triage', 'execute', 'verify', 'deliver'],
						current_stage: null,
						result: { files: ['a.md'] },
						completed_at: '2026-04-15T00:05:00Z'
					},
					created_at: '2026-04-15T00:05:00Z'
				}
			]
		});

		const m = detail.messages[0];
		if (m.role !== 'assistant') throw new Error('expected assistant message');
		expect(m.variant).toBe('task-resolved');
		expect(m.resolvedTask).toBeDefined();
		expect(m.resolvedTask!.agent).toBe('code-agent');
		expect(m.resolvedTask!.title).toBe('Svelte 5 notes');
		expect(m.resolvedTask!.summary).toContain('1 notes written');
	});

	it('wraps task.result into a generic ResultWidget artifact', () => {
		const detail = adaptThreadDetail({
			...baseThread,
			messages: [
				{
					id: 'msg-2b',
					thread_id: baseThread.id,
					role: 'assistant',
					content: 'code finished — svelte 5 notes.',
					variant: 'task-resolved',
					widgets: [],
					task_id: '01KP00000000000000000000BB',
					task: {
						id: '01KP00000000000000000000BB',
						type: 'code',
						title: 'Svelte 5 notes',
						status: 'completed',
						stages: ['execute'],
						current_stage: null,
						result: {
							status: 'ok',
							files: ['a.md'],
							source_url: 'https://example.com/x'
						},
						completed_at: '2026-04-15T00:05:00Z'
					},
					created_at: '2026-04-15T00:05:00Z'
				}
			]
		});

		const m = detail.messages[0];
		if (m.role !== 'assistant') throw new Error('expected assistant message');
		expect(m.resolvedTask!.artifact).toBeDefined();
		const artifact = m.resolvedTask!.artifact!;
		expect(artifact.tool).toBe('result');
		if (artifact.tool !== 'result') throw new Error('expected result widget');
		expect(artifact.label).toBe('code output');
		expect(artifact.data.files).toEqual(['a.md']);
		expect(artifact.data.source_url).toBe('https://example.com/x');
	});

	it('routes a code-agent result to the code.result widget shape', () => {
		const detail = adaptThreadDetail({
			...baseThread,
			messages: [
				{
					id: 'msg-code',
					thread_id: baseThread.id,
					role: 'assistant',
					content: 'code finished — rename tclient.',
					variant: 'task-resolved',
					widgets: [],
					task_id: '01KP00000000000000000000CD',
					task: {
						id: '01KP00000000000000000000CD',
						type: 'code',
						title: 'Rename tClient',
						status: 'completed',
						stages: ['triage', 'execute', 'verify', 'deliver'],
						current_stage: null,
						result: {
							pr_url: 'https://github.com/foo/bar/pull/42',
							branch: 'forge/01KP000000',
							claude_output: 'swapped identifier across 12 files.'
						},
						completed_at: '2026-04-15T00:05:00Z'
					},
					created_at: '2026-04-15T00:05:00Z'
				}
			]
		});

		const m = detail.messages[0];
		if (m.role !== 'assistant') throw new Error('expected assistant message');
		const artifact = m.resolvedTask!.artifact!;
		expect(artifact.tool).toBe('code.result');
		if (artifact.tool !== 'code.result') throw new Error('expected code.result');
		expect(artifact.prUrl).toBe('https://github.com/foo/bar/pull/42');
		expect(artifact.branch).toBe('forge/01KP000000');
		expect(artifact.claudeOutput).toContain('12 files');
	});

	it('omits artifact when task.result is empty or null', () => {
		const detail = adaptThreadDetail({
			...baseThread,
			messages: [
				{
					id: 'msg-2c',
					thread_id: baseThread.id,
					role: 'assistant',
					content: 'finished',
					variant: 'task-resolved',
					widgets: [],
					task_id: '01KP00000000000000000000CC',
					task: {
						id: '01KP00000000000000000000CC',
						type: 'echo',
						title: 'Echo task',
						status: 'completed',
						stages: ['execute'],
						current_stage: null,
						result: null,
						completed_at: '2026-04-15T00:05:00Z'
					},
					created_at: '2026-04-15T00:05:00Z'
				}
			]
		});

		const m = detail.messages[0];
		if (m.role !== 'assistant') throw new Error('expected assistant message');
		expect(m.resolvedTask!.artifact).toBeUndefined();
	});

	it('leaves dispatchedTask undefined when the task is missing (deleted row)', () => {
		const detail = adaptThreadDetail({
			...baseThread,
			messages: [
				{
					id: 'msg-3',
					thread_id: baseThread.id,
					role: 'assistant',
					content: 'dispatched ghost',
					variant: 'task-dispatched',
					widgets: [],
					task_id: '01KGHOST',
					task: null,
					created_at: '2026-04-15T00:00:01Z'
				}
			]
		});

		const m = detail.messages[0];
		if (m.role !== 'assistant') throw new Error('expected assistant message');
		expect(m.variant).toBe('task-dispatched');
		expect(m.dispatchedTask).toBeUndefined();
		expect(m.text).toBe('dispatched ghost');
	});
});
