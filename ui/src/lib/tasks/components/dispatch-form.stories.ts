import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import { expect, within } from 'storybook/test';
import DispatchForm from './dispatch-form.svelte';

const meta = {
	title: 'Tasks/DispatchForm',
	component: DispatchForm
} satisfies Meta<ComponentProps<typeof DispatchForm>>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		repos: [
			{ name: 't-eckert/ardent-forge', path: '', default_branch: 'main' },
			{ name: 't-eckert/dotfiles', path: '', default_branch: 'main' }
		]
	}
};

export const NoRepos: Story = {
	args: { repos: [] }
};

export const DisabledWhenEmpty: Story = {
	args: {
		repos: [{ name: 't-eckert/x', path: '', default_branch: 'main' }]
	},
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		await expect(canvas.getByText('DISPATCH A TASK')).toBeInTheDocument();
		await expect(canvas.getByRole('button', { name: /Dispatch/i })).toBeDisabled();
		await expect(canvas.getByRole('option', { name: 't-eckert/x' })).toBeInTheDocument();
	}
};
