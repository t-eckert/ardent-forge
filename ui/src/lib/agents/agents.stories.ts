import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import RunDetailHarness from './_stories/run-detail-harness.svelte';
import AgentsListHarness from './_stories/agents-list-harness.svelte';

const runDetailMeta = {
	title: 'Agents/Run detail',
	component: RunDetailHarness,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<ComponentProps<typeof RunDetailHarness>>;

export default runDetailMeta;

export const CodeAgentRun: StoryObj<ComponentProps<typeof RunDetailHarness>> = {
	name: 'code-agent · rename/t-client'
};

export const ListOnly: StoryObj<ComponentProps<typeof AgentsListHarness>> = {
	name: 'List only · no active run',
	render: () => ({ Component: AgentsListHarness })
};
