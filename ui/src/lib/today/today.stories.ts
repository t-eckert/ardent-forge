import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import TodayView from './views/today-view.svelte';

type Args = ComponentProps<typeof TodayView>;

const meta = {
	title: 'Today/Briefing canvas',
	component: TodayView,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<Args>;

export default meta;
type Story = StoryObj<Args>;

export const MorningBriefing: Story = {};
