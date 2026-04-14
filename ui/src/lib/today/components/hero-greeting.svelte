<script lang="ts">
	import { Display, Heading, Eyebrow, Stat, Meta } from '$lib/typography';
	import { formatDateFull } from '$lib/utils/date';

	interface Props {
		nowIso?: string;
		userName?: string;
		subtitle?: string;
		weatherTempC: number;
		weatherSummary: string;
		todosDue: number;
		todosDueNote?: string;
		agentsOvernight: number;
		agentsNote?: string;
	}

	let {
		nowIso = new Date().toISOString(),
		userName = 'Thomas',
		subtitle = 'The bench is lit. Three agents finished work overnight — and a long run wants your legs by 10.',
		weatherTempC,
		weatherSummary,
		todosDue,
		todosDueNote,
		agentsOvernight,
		agentsNote
	}: Props = $props();

	const dateLine = $derived(formatDateFull(nowIso).toUpperCase());
	const dayOfYear = $derived(dayOfYearFor(new Date(nowIso)));
	const year = $derived(new Date(nowIso).getFullYear());

	function dayOfYearFor(d: Date): number {
		const start = new Date(d.getFullYear(), 0, 0);
		const diff = d.getTime() - start.getTime();
		return Math.floor(diff / 86_400_000);
	}
</script>

<div class="flex items-end justify-between pb-[14px] border-b border-[var(--color-border)] gap-8">
	<div class="flex flex-col gap-1.5 min-w-0">
		<Eyebrow>{dateLine} · DAY {dayOfYear} OF {year}</Eyebrow>
		<Display size="xl">Good morning, {userName}.</Display>
		<Heading size="sm" italic>{subtitle}</Heading>
	</div>
	<div class="flex gap-7 flex-shrink-0">
		<div class="flex flex-col gap-1 items-start">
			<Eyebrow>OTTAWA</Eyebrow>
			<Stat value={weatherTempC} unit="°C" size="lg" />
			<Meta size="xs">{weatherSummary}</Meta>
		</div>
		<div class="flex flex-col gap-1 items-start">
			<Eyebrow>TODOS DUE</Eyebrow>
			<Stat value={todosDue} size="lg" />
			{#if todosDueNote}<Meta size="xs">{todosDueNote}</Meta>{/if}
		</div>
		<div class="flex flex-col gap-1 items-start">
			<Eyebrow>AGENT RUNS</Eyebrow>
			<Stat value={agentsOvernight} size="lg" />
			{#if agentsNote}<Meta size="xs">{agentsNote}</Meta>{/if}
		</div>
	</div>
</div>
