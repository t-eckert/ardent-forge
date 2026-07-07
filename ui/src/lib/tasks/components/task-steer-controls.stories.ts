import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import { expect, within, userEvent, spyOn, waitFor } from 'storybook/test';
import TaskSteerControls from './task-steer-controls.svelte';

const baseTask = {
	id: '01HZX9MVT0EXAMPLE0000000000',
	type: 'code',
	status: 'queued',
	source: 'manual',
	title: 't',
	description: 'd',
	handler_data: {},
	result: null,
	retries: 0,
	require_approval: false,
	continues_task_id: null,
	created_at: '2026-06-20T00:00:00+00:00',
	updated_at: '2026-06-20T00:00:00+00:00',
	referenced_by_thread_ids: []
};

const meta = {
	title: 'Tasks/TaskSteerControls',
	component: TaskSteerControls
} satisfies Meta<ComponentProps<typeof TaskSteerControls>>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Active: Story = {
	args: { task: { ...baseTask, status: 'executing', handler_data: { zellij_session: 'agent-x' } } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await expect(canvas.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
		await expect(canvas.getByRole('button', { name: /attach/i })).toBeInTheDocument();
		await expect(canvas.queryByRole('button', { name: 'Approve' })).toBeNull();
	}
};

export const AwaitingApproval: Story = {
	args: { task: { ...baseTask, status: 'awaiting_approval' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await expect(canvas.getByRole('button', { name: 'Approve' })).toBeInTheDocument();
		await expect(canvas.getByRole('button', { name: 'Reject' })).toBeInTheDocument();
		await expect(canvas.getByRole('button', { name: 'Follow up' })).toBeInTheDocument();
	}
};

export const Failed: Story = {
	args: { task: { ...baseTask, status: 'failed' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await expect(canvas.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
		await expect(canvas.getByRole('button', { name: 'Follow up' })).toBeInTheDocument();
	}
};

export const Completed: Story = {
	args: { task: { ...baseTask, status: 'completed' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await expect(canvas.getByRole('button', { name: 'Follow up' })).toBeInTheDocument();
		await expect(canvas.queryByRole('button', { name: 'Cancel' })).toBeNull();
	}
};

export const CompletedNonCode: Story = {
	args: { task: { ...baseTask, type: 'echo', status: 'completed' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await expect(canvas.queryByRole('button', { name: 'Follow up' })).toBeNull();
	}
};

export const Cancelled: Story = {
	args: { task: { ...baseTask, status: 'cancelled' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await expect(canvas.queryByRole('button')).toBeNull();
	}
};

export const CancelRequiresTwoClicks: Story = {
	args: { task: { ...baseTask, status: 'executing' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		const fetchSpy = spyOn(window, 'fetch').mockResolvedValue({
			ok: true,
			status: 200,
			json: () => Promise.resolve(baseTask),
			text: () => Promise.resolve('{}')
		} as Response);
		try {
			await userEvent.click(canvas.getByRole('button', { name: 'Cancel' }));
			await expect(canvas.getByRole('button', { name: 'Confirm?' })).toBeInTheDocument();
			await expect(fetchSpy).not.toHaveBeenCalled();
			await userEvent.click(canvas.getByRole('button', { name: 'Confirm?' }));
			await waitFor(() =>
				expect(fetchSpy).toHaveBeenCalledWith(
					expect.stringContaining('/api/tasks/01HZX9MVT0EXAMPLE0000000000/cancel'),
					expect.objectContaining({ method: 'POST' })
				)
			);
		} finally {
			fetchSpy.mockRestore();
		}
	}
};

export const ApproveCallsEndpoint: Story = {
	args: { task: { ...baseTask, status: 'awaiting_approval' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		const fetchSpy = spyOn(window, 'fetch').mockResolvedValue({
			ok: true,
			status: 200,
			json: () => Promise.resolve({ ...baseTask, status: 'delivering' }),
			text: () => Promise.resolve('{}')
		} as Response);
		try {
			await userEvent.click(canvas.getByRole('button', { name: 'Approve' }));
			await waitFor(() =>
				expect(fetchSpy).toHaveBeenCalledWith(
					expect.stringContaining('/api/tasks/01HZX9MVT0EXAMPLE0000000000/approve'),
					expect.objectContaining({ method: 'POST' })
				)
			);
		} finally {
			fetchSpy.mockRestore();
		}
	}
};

export const RejectRequiresTwoClicks: Story = {
	args: { task: { ...baseTask, status: 'awaiting_approval' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		const fetchSpy = spyOn(window, 'fetch').mockResolvedValue({
			ok: true,
			status: 200,
			json: () => Promise.resolve({ ...baseTask, status: 'cancelled' }),
			text: () => Promise.resolve('{}')
		} as Response);
		try {
			await userEvent.click(canvas.getByRole('button', { name: 'Reject' }));
			await expect(canvas.getByRole('button', { name: 'Confirm?' })).toBeInTheDocument();
			// Approve stays put — only the reject button arms.
			await expect(canvas.getByRole('button', { name: 'Approve' })).toBeInTheDocument();
			await expect(fetchSpy).not.toHaveBeenCalled();
			await userEvent.click(canvas.getByRole('button', { name: 'Confirm?' }));
			await waitFor(() =>
				expect(fetchSpy).toHaveBeenCalledWith(
					expect.stringContaining('/api/tasks/01HZX9MVT0EXAMPLE0000000000/reject'),
					expect.objectContaining({ method: 'POST' })
				)
			);
		} finally {
			fetchSpy.mockRestore();
		}
	}
};

export const FollowUpSendDisabledUntilPrompt: Story = {
	args: { task: { ...baseTask, status: 'completed' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await userEvent.click(canvas.getByRole('button', { name: 'Follow up' }));
		const send = canvas.getByRole('button', { name: 'Send' });
		await expect(send).toBeDisabled();
		await userEvent.type(canvas.getByRole('textbox', { name: 'Follow-up prompt' }), '  ');
		await expect(send).toBeDisabled();
		await userEvent.type(canvas.getByRole('textbox', { name: 'Follow-up prompt' }), 'do more');
		await expect(send).toBeEnabled();
	}
};

export const FollowUpSubmitsPrompt: Story = {
	args: { task: { ...baseTask, status: 'completed' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		const fetchSpy = spyOn(window, 'fetch').mockResolvedValue({
			ok: true,
			status: 200,
			json: () => Promise.resolve({ ...baseTask, id: '01HZX9MVT0EXAMPLE0000000001' }),
			text: () => Promise.resolve('{}')
		} as Response);
		try {
			await userEvent.click(canvas.getByRole('button', { name: 'Follow up' }));
			await userEvent.type(
				canvas.getByRole('textbox', { name: 'Follow-up prompt' }),
				'also update the docs'
			);
			await userEvent.click(canvas.getByRole('button', { name: 'Send' }));
			await waitFor(() =>
				expect(fetchSpy).toHaveBeenCalledWith(
					expect.stringContaining('/api/tasks/01HZX9MVT0EXAMPLE0000000000/follow-up'),
					expect.objectContaining({
						method: 'POST',
						body: JSON.stringify({ prompt: 'also update the docs' })
					})
				)
			);
		} finally {
			fetchSpy.mockRestore();
		}
	}
};

export const FailedActionSurfacesAlert: Story = {
	args: { task: { ...baseTask, status: 'failed' } },
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		const fetchSpy = spyOn(window, 'fetch').mockResolvedValue({
			ok: false,
			status: 500,
			json: () => Promise.resolve({}),
			text: () => Promise.resolve('boom')
		} as Response);
		try {
			await userEvent.click(canvas.getByRole('button', { name: 'Retry' }));
			await waitFor(() => expect(canvas.getByRole('alert')).toBeInTheDocument());
			await expect(canvas.getByRole('alert')).toHaveTextContent(/500/);
		} finally {
			fetchSpy.mockRestore();
		}
	}
};
