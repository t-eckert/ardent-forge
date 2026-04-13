<script lang="ts">
	import { Card } from '$lib/components';
	import { Eyebrow, Stat, Meta } from '$lib/typography';

	interface Props {
		score?: number;
		hrv?: string;
		hrvDelta?: string;
		rhr?: string;
		rhrDelta?: string;
		sleep?: string;
		load?: string;
	}

	let {
		score = 82,
		hrv = '64 ms',
		hrvDelta = '+3',
		rhr = '48 bpm',
		rhrDelta = '–2',
		sleep = '7h 22m',
		load = 'Optimal'
	}: Props = $props();
</script>

<Card surface="paper">
	<div class="flex flex-col gap-3.5 p-[18px]">
		<div class="flex items-end justify-between">
			<Eyebrow>READINESS · 7D</Eyebrow>
			<Stat value={score} unit="/100" size="xl" />
		</div>
		<div class="flex flex-col gap-2.5 text-[13px]">
			<div class="flex items-baseline justify-between">
				<Eyebrow>HRV</Eyebrow>
				<span class="inline-flex items-baseline gap-1.5">
					<Stat value={hrv} size="sm" />
					<Meta tone="moss">{hrvDelta}</Meta>
				</span>
			</div>
			<div class="flex items-baseline justify-between">
				<Eyebrow>RHR</Eyebrow>
				<span class="inline-flex items-baseline gap-1.5">
					<Stat value={rhr} size="sm" />
					<Meta tone="moss">{rhrDelta}</Meta>
				</span>
			</div>
			<div class="flex items-baseline justify-between">
				<Eyebrow>SLEEP</Eyebrow>
				<Stat value={sleep} size="sm" />
			</div>
			<div class="flex items-baseline justify-between">
				<Eyebrow>LOAD</Eyebrow>
				<Stat value={load} size="sm" />
			</div>
		</div>
	</div>
</Card>
