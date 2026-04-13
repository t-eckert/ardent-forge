import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import WidgetHarness from '../_stories/widget-harness.svelte';
import { makeWorkouts } from '$lib/mocks/widgets/workouts';

type Args = ComponentProps<typeof WidgetHarness>;

const meta = {
	title: 'Widgets/health.workouts',
	component: WidgetHarness,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<Args>;

export default meta;
type Story = StoryObj<Args>;

export const HalfMarathonBlock: Story = { args: { payload: makeWorkouts() } };
