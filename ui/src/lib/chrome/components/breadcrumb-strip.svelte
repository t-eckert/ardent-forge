<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { BreadcrumbSegment } from '$lib/chrome/state/chrome.state.svelte';
	import { Meta } from '$lib/typography';
	import { Chip } from '$lib/components';
	import { cn } from '$lib/utils/cn';

	interface Props {
		/** If empty, nothing renders (top-level surfaces have no strip) */
		trail: BreadcrumbSegment[];
		/** Optional status chip — live indicator, tool badge, etc. */
		statusChip?: { label: string; tone?: 'ember' | 'moss' | 'neutral' };
		/** Right-side meta line (e.g. "strava synced · 4m") */
		rightMeta?: string;
		/** Right-side actions slot */
		actions?: Snippet;
		class?: string;
	}

	let { trail, statusChip, rightMeta, actions, class: klass }: Props = $props();
</script>

{#if trail.length > 0}
	<div
		class={cn(
			'flex items-center justify-between h-12 px-8 border-b border-[var(--color-border)] bg-[var(--color-paper)]',
			klass
		)}
	>
		<div class="flex items-center gap-2 font-mono text-[12px]">
			{#each trail as segment, i (segment.label)}
				{#if i > 0}
					<span class="text-[var(--color-graphite)]">/</span>
				{/if}
				{#if segment.href}
					<a
						href={segment.href}
						class="text-[var(--color-slate)] hover:text-[var(--color-ink)] transition-colors"
					>
						{segment.label}
					</a>
				{:else}
					<span class="text-[var(--color-ink)]">{segment.label}</span>
				{/if}
			{/each}
			{#if statusChip}
				<Chip tone={statusChip.tone ?? 'neutral'}>{statusChip.label}</Chip>
			{/if}
		</div>
		<div class="flex items-center gap-2.5">
			{#if rightMeta}
				<Meta size="xs">{rightMeta}</Meta>
			{/if}
			{#if actions}
				{@render actions()}
			{/if}
		</div>
	</div>
{/if}
