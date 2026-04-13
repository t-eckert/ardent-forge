<script lang="ts">
	import type { Snippet } from 'svelte';
	import { Card } from '$lib/components';
	import { Eyebrow, Stat, Meta } from '$lib/typography';

	interface Props {
		label: string;
		value: string | number;
		unit?: string;
		delta?: string;
		deltaTone?: 'moss' | 'ember' | 'muted';
		children?: Snippet;
	}

	let {
		label,
		value,
		unit,
		delta,
		deltaTone = 'moss',
		children
	}: Props = $props();
</script>

<Card surface="paper">
	<div class="flex flex-col gap-1 p-[18px]">
		<div class="flex items-center justify-between">
			<Eyebrow>{label}</Eyebrow>
			{#if delta}<Meta tone={deltaTone}>{delta}</Meta>{/if}
		</div>
		<Stat {value} {unit} size="xl" />
		{#if children}
			<div class="pt-2">
				{@render children()}
			</div>
		{/if}
	</div>
</Card>
