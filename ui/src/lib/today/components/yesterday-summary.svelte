<script lang="ts">
	import { Heading, Stat } from '$lib/typography';

	interface Row {
		label: string;
		value: string;
	}

	interface Props {
		rows: Row[];
	}

	let { rows }: Props = $props();
</script>

<section class="flex flex-col gap-2.5">
	<header class="flex items-end justify-between pb-1.5 border-b border-[var(--color-border)]">
		<Heading size="md">Yesterday</Heading>
		<a href="/library/log" class="font-mono text-[11px] text-[var(--color-ember-deep)]">
			open log →
		</a>
	</header>
	<div class="flex flex-col gap-1.5">
		{#each rows as row (row.label)}
			<div class="flex items-center justify-between text-[13px]">
				<span class="text-[var(--color-ink)]">{row.label}</span>
				<Stat value={row.value} size="sm" />
			</div>
		{/each}
	</div>
</section>
