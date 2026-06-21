import { describe, it, expect } from 'vitest';
import { Task, TaskStatus } from './task';

const base = {
	id: '01HZX9MVT0EXAMPLE0000000000',
	type: 'code',
	status: 'queued',
	source: 'manual',
	title: 't',
	description: 'd',
	created_at: '2026-06-20T00:00:00+00:00',
	updated_at: '2026-06-20T00:00:00+00:00'
};

describe('Task schema — phase 2 statuses', () => {
	it('parses awaiting_approval', () => {
		const t = Task.parse({ ...base, status: 'awaiting_approval' });
		expect(t.status).toBe('awaiting_approval');
	});

	it('parses cancelled', () => {
		const t = Task.parse({ ...base, status: 'cancelled' });
		expect(t.status).toBe('cancelled');
	});

	it('round-trips require_approval and continues_task_id', () => {
		const t = Task.parse({
			...base,
			status: 'queued',
			require_approval: true,
			continues_task_id: '01HZX9MVT0PARENT00000000000'
		});
		expect(t.require_approval).toBe(true);
		expect(t.continues_task_id).toBe('01HZX9MVT0PARENT00000000000');
	});

	it('defaults require_approval to false when absent', () => {
		const t = Task.parse(base);
		expect(t.require_approval).toBe(false);
	});

	it('TaskStatus enum includes the new states', () => {
		expect(TaskStatus.options).toContain('awaiting_approval');
		expect(TaskStatus.options).toContain('cancelled');
	});
});
