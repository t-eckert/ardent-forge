import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
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
