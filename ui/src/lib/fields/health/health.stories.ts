import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import HealthWorkouts from './views/health-workouts.svelte';

type Args = ComponentProps<typeof HealthWorkouts>;

const meta = {
	title: 'Fields/Health · Workouts',
	component: HealthWorkouts,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<Args>;

export default meta;
type Story = StoryObj<Args>;

export const Default: Story = {};
