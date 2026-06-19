import type { Meta, StoryObj } from '@storybook/sveltekit';
import SidebarHarness from '../_stories/sidebar-harness.svelte';
import type { ComponentProps } from 'svelte';

type Args = ComponentProps<typeof SidebarHarness>;

const meta = {
	title: 'Chrome/Sidebar',
	component: SidebarHarness,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<Args>;

export default meta;
type Story = StoryObj<Args>;

export const TodayActive: Story = { args: { active: 'today' } };
export const AgentsActive: Story = { args: { active: 'agents' } };
export const SchedulesActive: Story = { args: { active: 'schedules' } };
export const TasksActive: Story = { args: { active: 'tasks' } };
export const NoActive: Story = { args: { active: null } };
