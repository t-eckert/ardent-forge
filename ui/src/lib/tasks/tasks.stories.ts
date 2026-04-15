import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import TaskListHarness from './_stories/task-list-harness.svelte';
import TaskDetailHarness from './_stories/task-detail-harness.svelte';

type DetailArgs = ComponentProps<typeof TaskDetailHarness>;

const meta = {
	title: 'Tasks/List + Detail',
	component: TaskDetailHarness,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<DetailArgs>;

export default meta;

export const ListOnly: StoryObj<ComponentProps<typeof TaskListHarness>> = {
	name: 'List · mixed statuses',
	render: () => ({ Component: TaskListHarness })
};

export const ResolvedResearch: StoryObj<DetailArgs> = {
	name: 'Detail · completed research task',
	args: { activeId: '01KP000000000000000000RSRC' }
};

export const ExecutingCode: StoryObj<DetailArgs> = {
	name: 'Detail · code task in flight',
	args: { activeId: '01KP000000000000000000CODE' }
};

export const FailedTickets: StoryObj<DetailArgs> = {
	name: 'Detail · failed tickets task',
	args: { activeId: '01KP000000000000000000TCKT' }
};
