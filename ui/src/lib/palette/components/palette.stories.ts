import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import PaletteHarness from '../_stories/palette-harness.svelte';

type Args = ComponentProps<typeof PaletteHarness>;

const meta = {
	title: 'Palette/Command',
	component: PaletteHarness,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<Args>;

export default meta;
type Story = StoryObj<Args>;

export const Open: Story = { args: { openOnMount: true } };
export const Closed: Story = { args: { openOnMount: false } };
