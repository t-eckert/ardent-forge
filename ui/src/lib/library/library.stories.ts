import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import LibraryIndex from './views/library-index.svelte';

type Args = ComponentProps<typeof LibraryIndex>;

const meta = {
	title: 'Library/Index',
	component: LibraryIndex,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<Args>;

export default meta;
type Story = StoryObj<Args>;

export const Default: Story = {};

export const WithCounts: Story = {
	args: {
		agentCount: 4,
		connectorCount: 5,
		memoryCount: 12,
		scheduleCount: 3
	}
};
