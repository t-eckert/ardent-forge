import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import ThreadViewHarness from './_stories/thread-view-harness.svelte';
import ThreadsListHarness from './_stories/threads-list-harness.svelte';

const threadViewMeta = {
	title: 'Threads/Thread view',
	component: ThreadViewHarness,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<ComponentProps<typeof ThreadViewHarness>>;

export default threadViewMeta;

export const WithCodeDiff: StoryObj<ComponentProps<typeof ThreadViewHarness>> = {
	name: 'With code.diff widget'
};

// List-only harness gets its own story via the second component export
export const ListOnly: StoryObj<ComponentProps<typeof ThreadsListHarness>> = {
	name: 'List only · no active thread',
	render: () => ({ Component: ThreadsListHarness })
};
