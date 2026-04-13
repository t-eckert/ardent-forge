import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import WidgetHarness from '../_stories/widget-harness.svelte';
import { makePlacesMap } from '$lib/mocks/widgets/places-map';

type Args = ComponentProps<typeof WidgetHarness>;

const meta = {
	title: 'Widgets/places.map',
	component: WidgetHarness,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<Args>;

export default meta;
type Story = StoryObj<Args>;

export const PizzaInOttawa: Story = { args: { payload: makePlacesMap() } };
