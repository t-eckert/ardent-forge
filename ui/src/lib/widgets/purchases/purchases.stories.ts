import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import WidgetHarness from '../_stories/widget-harness.svelte';
import { makePurchases } from '$lib/mocks/widgets/purchases';

type Args = ComponentProps<typeof WidgetHarness>;

const meta = {
	title: 'Widgets/finance.purchases',
	component: WidgetHarness,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<Args>;

export default meta;
type Story = StoryObj<Args>;

export const ThisWeek: Story = { args: { payload: makePurchases() } };
