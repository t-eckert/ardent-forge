<script lang="ts">
	import BreadcrumbStrip from '../components/breadcrumb-strip.svelte';
	import Button from '$lib/components/button.svelte';
	import type { BreadcrumbSegment } from '../state/chrome.state.svelte';

	interface Props {
		trail: BreadcrumbSegment[];
		statusChip?: { label: string; tone?: 'ember' | 'moss' | 'neutral' };
		rightMeta?: string;
		showActions?: boolean;
	}

	let { trail, statusChip, rightMeta, showActions = false }: Props = $props();
</script>

<div class="bg-[var(--color-paper)] min-h-[100px]">
	<BreadcrumbStrip {trail} {statusChip} {rightMeta}>
		{#snippet actions()}
			{#if showActions}
				<Button variant="secondary" size="sm">Pin</Button>
				<Button variant="primary" size="sm">Edit</Button>
			{/if}
		{/snippet}
	</BreadcrumbStrip>
</div>
