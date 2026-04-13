<script lang="ts">
	import { Heading, Meta } from '$lib/typography';

	interface DayCell {
		dow: string;
		date: string;
		title: string;
		source: string;
		sourceTone?: 'ember' | 'muted';
		status: 'done' | 'today' | 'open';
		highlight?: boolean;
	}

	interface Props {
		days: DayCell[];
		blockLabel?: string;
	}

	let { days, blockLabel = 'BLOCK WK 8 · BUILD' }: Props = $props();

	const statusMap = {
		done: { label: '■ done', bg: '#E8F0E6', fg: '#3C6A4A' },
		today: { label: '▸ today', bg: '#FCE6DD', fg: 'var(--color-ember-deep)' },
		open: { label: '○ open', bg: 'var(--color-bench)', fg: 'var(--color-graphite)' }
	} as const;
</script>

<section class="flex flex-col gap-3.5">
	<header class="flex items-end justify-between pb-2 border-b border-[var(--color-border)]">
		<div class="flex items-baseline gap-2.5">
			<Heading size="md">This week</Heading>
			<Meta size="sm">{blockLabel}</Meta>
		</div>
		<a href="#plan" class="font-mono text-[11px] text-[var(--color-ember-deep)]">view plan →</a>
	</header>
	<div class="grid grid-cols-7 gap-2">
		{#each days as day (day.dow)}
			{@const st = statusMap[day.status]}
			<div
				class="flex flex-col gap-2 p-2.5 border rounded-[4px] min-h-[140px]"
				style={day.highlight
					? 'background: #FFF5EF; border-color: var(--color-ember);'
					: 'background: var(--color-paper); border-color: var(--color-border);'}
			>
				<div class="flex items-center justify-between">
					<span
						class="font-mono text-[10px]"
						style="color: {day.highlight
							? 'var(--color-ember)'
							: 'var(--color-graphite)'};"
					>
						{day.dow}
					</span>
					<span class="font-mono text-[10px] text-[var(--color-graphite)]">{day.date}</span>
				</div>
				<span class="text-[12px] font-medium text-[var(--color-ink)]">{day.title}</span>
				<Meta size="xs" tone={day.sourceTone ?? 'muted'}>{day.source}</Meta>
				<div class="mt-auto">
					<span
						class="inline-block px-1.5 py-[2px] font-mono text-[10px] rounded-[2px]"
						style="background: {st.bg}; color: {st.fg};"
					>
						{st.label}
					</span>
				</div>
			</div>
		{/each}
	</div>
</section>
