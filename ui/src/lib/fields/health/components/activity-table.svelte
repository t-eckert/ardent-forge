<script lang="ts">
	import { Heading, Meta, Stat } from '$lib/typography';
	import { Chip } from '$lib/components';

	interface ActivityRow {
		date: string;
		title: string;
		type: string;
		volume: string;
		intensity: string;
		source: 'strava' | 'notebook';
	}

	interface Props {
		rows: ActivityRow[];
		blockCount?: number;
	}

	let { rows, blockCount = 28 }: Props = $props();
</script>

<section class="flex flex-col gap-2.5">
	<header class="flex items-end justify-between pb-2 border-b border-[var(--color-border)]">
		<div class="flex items-baseline gap-2.5">
			<Heading size="md">Recent activity</Heading>
			<Meta size="sm">{blockCount} THIS BLOCK</Meta>
		</div>
		<a href="#all" class="font-mono text-[11px] text-[var(--color-ember-deep)]">view all →</a>
	</header>
	<div
		class="grid grid-cols-[70px_1fr_90px_140px_160px_80px] px-1.5 py-2 border-b border-[var(--color-border)] font-mono text-[10px] tracking-wider text-[var(--color-graphite)]"
	>
		<span>DATE</span><span>TITLE</span><span>TYPE</span><span>VOLUME</span><span
			>HR · INTENSITY</span
		><span>SOURCE</span>
	</div>
	{#each rows as row, i (i)}
		<div
			class="grid grid-cols-[70px_1fr_90px_140px_160px_80px] items-center px-1.5 py-2.5 text-[13px]"
			class:border-b={i < rows.length - 1}
			style={i < rows.length - 1 ? 'border-color: var(--color-border)' : ''}
		>
			<span class="font-mono text-[var(--color-graphite)] text-[12px]">{row.date}</span>
			<span class="text-[var(--color-ink)]">{row.title}</span>
			<span class="text-[var(--color-slate)]">{row.type}</span>
			<span class="font-mono text-[12px]">{row.volume}</span>
			<span class="text-[var(--color-slate)] text-[12px]">{row.intensity}</span>
			<span>
				<Chip tone={row.source === 'strava' ? 'ember' : 'neutral'}>{row.source}</Chip>
			</span>
		</div>
	{/each}
</section>
