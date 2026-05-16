<script lang="ts">
	import type { Component } from 'svelte';
	import { ArrowRight } from '$lib/icons';
	import { Heading, Meta } from '$lib/typography';
	import { Card } from '$lib/components';

	interface Props {
		title: string;
		description: string;
		href: string;
		icon?: Component;
	}

	let { title, description, href, icon: Icon }: Props = $props();
</script>

<a
	{href}
	target="_blank"
	rel="noopener noreferrer"
	class="block group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ember)] rounded-[8px]"
>
	<Card>
		<div class="flex items-start gap-4 p-4">
			{#if Icon}
				<div
					class="flex items-center justify-center w-9 h-9 rounded-md bg-[var(--color-bench)] text-[var(--color-ink)] flex-shrink-0"
				>
					<Icon size={18} weight="regular" />
				</div>
			{/if}
			<div class="flex flex-col gap-0.5 min-w-0 flex-1">
				<Heading size="sm">{title}</Heading>
				<Meta size="sm">{description}</Meta>
				<Meta size="xs" class="text-[var(--color-graphite)] truncate mt-1 font-mono">{href}</Meta>
			</div>
			<div
				class="text-[var(--color-graphite)] group-hover:text-[var(--color-ink)] transition-colors mt-1.5 flex-shrink-0"
			>
				<ArrowRight size={16} weight="regular" />
			</div>
		</div>
	</Card>
</a>
