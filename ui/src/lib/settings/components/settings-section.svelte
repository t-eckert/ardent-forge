<script lang="ts">
	import type { Snippet } from 'svelte';
	import { Eyebrow, Heading, Body } from '$lib/typography';

	interface Props {
		eyebrow: string;
		title: string;
		description?: string;
		children: Snippet;
	}

	let { eyebrow, title, description, children }: Props = $props();
</script>

<section class="flex flex-col gap-4 py-7 border-b border-[var(--color-border)] last:border-b-0">
	<div class="flex flex-col gap-1">
		<Eyebrow>{eyebrow}</Eyebrow>
		<Heading size="md">{title}</Heading>
		{#if description}
			<Body size="sm" muted class="max-w-prose">{description}</Body>
		{/if}
	</div>
	<div>
		{@render children()}
	</div>
</section>
