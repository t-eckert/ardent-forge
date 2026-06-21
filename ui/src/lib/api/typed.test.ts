import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

const { api, ApiError } = await import('./typed');

const task = {
	id: '01HZX9MVT0EXAMPLE0000000000',
	type: 'code',
	status: 'queued',
	source: 'manual',
	title: 't',
	description: 'd',
	handler_data: {},
	retries: 0,
	require_approval: false,
	created_at: '2026-06-20T00:00:00+00:00',
	updated_at: '2026-06-20T00:00:00+00:00'
};

function ok(data: unknown, status = 200) {
	return {
		ok: status >= 200 && status < 300,
		status,
		json: () => Promise.resolve(data),
		text: () => Promise.resolve(JSON.stringify(data))
	};
}

beforeEach(() => mockFetch.mockReset());

describe('api.tasks steer mutations', () => {
	it('cancel POSTs to the cancel endpoint', async () => {
		mockFetch.mockResolvedValueOnce(ok(task));
		await api.tasks.cancel('abc');
		expect(mockFetch).toHaveBeenCalledWith(
			'/api/tasks/abc/cancel',
			expect.objectContaining({ method: 'POST' })
		);
	});

	it('approve POSTs to the approve endpoint', async () => {
		mockFetch.mockResolvedValueOnce(ok(task));
		await api.tasks.approve('abc');
		expect(mockFetch).toHaveBeenCalledWith(
			'/api/tasks/abc/approve',
			expect.objectContaining({ method: 'POST' })
		);
	});

	it('reject POSTs to the reject endpoint', async () => {
		mockFetch.mockResolvedValueOnce(ok(task));
		await api.tasks.reject('abc');
		expect(mockFetch).toHaveBeenCalledWith(
			'/api/tasks/abc/reject',
			expect.objectContaining({ method: 'POST' })
		);
	});

	it('retry POSTs to the retry endpoint', async () => {
		mockFetch.mockResolvedValueOnce(ok(task));
		await api.tasks.retry('abc');
		expect(mockFetch).toHaveBeenCalledWith(
			'/api/tasks/abc/retry',
			expect.objectContaining({ method: 'POST' })
		);
	});

	it('followUp POSTs the prompt body and returns the new task', async () => {
		mockFetch.mockResolvedValueOnce(ok({ ...task, id: 'new-id', continues_task_id: 'abc' }));
		const created = await api.tasks.followUp('abc', 'do the thing');
		expect(mockFetch).toHaveBeenCalledWith(
			'/api/tasks/abc/follow-up',
			expect.objectContaining({ method: 'POST', body: JSON.stringify({ prompt: 'do the thing' }) })
		);
		expect(created.id).toBe('new-id');
	});

	it('throws ApiError on a 409', async () => {
		mockFetch.mockResolvedValueOnce({
			ok: false,
			status: 409,
			text: () => Promise.resolve('Cannot cancel a completed task')
		});
		await expect(api.tasks.cancel('abc')).rejects.toThrow(ApiError);
	});
});
