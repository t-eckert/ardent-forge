import type { Meta, StoryObj } from '@storybook/sveltekit';
import type { ComponentProps } from 'svelte';
import CodeDiffHarness from '../_stories/code-diff-harness.svelte';
import { makeCodeDiff, makeLargeCodeDiff } from '$lib/mocks/widgets/code-diff';

type Args = ComponentProps<typeof CodeDiffHarness>;

const meta = {
	title: 'Widgets/code.diff',
	component: CodeDiffHarness,
	parameters: { layout: 'fullscreen' }
} satisfies Meta<Args>;

export default meta;
type Story = StoryObj<Args>;

export const Default: Story = {
	name: 'Default — rename/t-client',
	args: { payload: makeCodeDiff() }
};

export const NoHunk: Story = {
	name: 'No hunk preview',
	args: {
		payload: makeCodeDiff({
			files: [
				{ path: 'coordinator.go', changes: 6, additions: 6, deletions: 6 },
				{ path: 'tick.go', changes: 4, additions: 4, deletions: 4 }
			]
		})
	}
};

export const ManyFiles: Story = {
	name: 'Many files (volume)',
	args: { payload: makeLargeCodeDiff(18) }
};

export const ApproveAndMerge: Story = {
	name: 'PR ready — approve & merge',
	args: {
		payload: makeCodeDiff({
			footerMeta: 'tests green · lint clean · ready to merge',
			actions: [
				{ kind: 'view-diff', label: 'View diff' },
				{ kind: 'request-changes', label: 'Request changes' },
				{ kind: 'approve-merge', label: 'Approve & merge' }
			]
		})
	}
};
