import type { Meta, StoryObj } from '@storybook/sveltekit';
import TypographyShowcase from './_typography-showcase.svelte';

const meta: Meta<typeof TypographyShowcase> = {
	title: 'Typography/Showcase',
	component: TypographyShowcase
};

export default meta;
type Story = StoryObj<typeof meta>;

export const AllPrimitives: Story = {};
