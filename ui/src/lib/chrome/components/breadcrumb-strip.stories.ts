import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import BreadcrumbHarness from '../_stories/breadcrumb-harness.svelte';

type Args = ComponentProps<typeof BreadcrumbHarness>;

const meta = {
	title: 'Chrome/Breadcrumb strip',
	component: BreadcrumbHarness,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<Args>;

export default meta;
type Story = StoryObj<Args>;

export const TopLevelHidden: Story = {
	name: 'A · top-level (no strip)',
	args: { trail: [] }
};

export const Nested: Story = {
	name: 'B · nested (2 levels)',
	args: {
		trail: [
			{ label: 'Library', href: '/library' },
			{ label: 'Memory' }
		],
		showActions: true
	}
};

export const DeepWithLive: Story = {
	name: 'C · deep (3+ levels) with live',
	args: {
		trail: [
			{ label: 'Library', href: '/library' },
			{ label: 'Memory', href: '/library/memory' },
			{ label: 'Notes' }
		],
		statusChip: { label: '● live', tone: 'moss' },
		rightMeta: 'notebook synced · 4m',
		showActions: true
	}
};

export const Thread: Story = {
	name: 'D · thread (named conversation)',
	args: {
		trail: [
			{ label: 'Threads', href: '/threads' },
			{ label: 'Morning briefing' }
		],
		statusChip: { label: 'code+tools', tone: 'ember' },
		rightMeta: 'last activity · 06:12'
	}
};
