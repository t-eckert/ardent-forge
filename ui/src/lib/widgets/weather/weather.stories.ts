import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import WidgetHarness from '../_stories/widget-harness.svelte';
import { makeWeather } from '$lib/mocks/widgets/weather';

type Args = ComponentProps<typeof WidgetHarness>;

const meta = {
	title: 'Widgets/weather.forecast',
	component: WidgetHarness,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<Args>;

export default meta;
type Story = StoryObj<Args>;

export const Ottawa: Story = { args: { payload: makeWeather() } };
