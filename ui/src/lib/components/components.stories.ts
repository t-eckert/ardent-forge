import type { Meta, StoryObj } from '@storybook/sveltekit';
import ComponentShowcase from './_components-showcase.svelte';

const meta: Meta<typeof ComponentShowcase> = {
	title: 'Components/Primitives',
	component: ComponentShowcase
};

export default meta;
type Story = StoryObj<typeof meta>;

export const AllPrimitives: Story = {};
