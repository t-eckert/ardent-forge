import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import WidgetHarness from '../_stories/widget-harness.svelte';
import { makeResearchResult, makeCodeResult } from '$lib/mocks/widgets/result';

type Args = ComponentProps<typeof WidgetHarness>;

const meta = {
	title: 'Widgets/result',
	component: WidgetHarness,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<Args>;

export default meta;
type Story = StoryObj<Args>;

export const Research: Story = { args: { payload: makeResearchResult() } };
export const Code: Story = { args: { payload: makeCodeResult() } };
export const Empty: Story = {
	args: { payload: { tool: 'result', label: 'empty', data: {} } }
};
