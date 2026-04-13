import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import FieldsIndexHarness from './_stories/fields-index-harness.svelte';

type Args = ComponentProps<typeof FieldsIndexHarness>;

const meta = {
	title: 'Library/Fields index',
	component: FieldsIndexHarness,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<Args>;

export default meta;
type Story = StoryObj<Args>;

export const Default: Story = {};
