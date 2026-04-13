<script lang="ts">
	import { Card } from '$lib/components';
	import { Display, Body, Eyebrow, Stat } from '$lib/typography';

	interface Props {
		goal: string;
		event: string;
		daysToRace: number;
		blockLabel: string;
		goalPace: string;
		thresholdNote: string;
	}

	let { goal, event, daysToRace, blockLabel, goalPace, thresholdNote }: Props = $props();
</script>

<div class="flex border border-[var(--color-border)] rounded-lg overflow-hidden">
	<div
		class="flex flex-col gap-1.5 p-[22px_26px] flex-1 text-[var(--color-paper)]"
		style="background: linear-gradient(135deg, #E34E18 0%, #C73D0F 100%);"
	>
		<span class="font-mono text-[10px] tracking-[0.12em] opacity-85">CURRENT GOAL</span>
		<Display size="md" class="text-[var(--color-paper)]">{goal}</Display>
		<Body size="sm" class="text-[var(--color-paper)] opacity-90">{event}</Body>
	</div>
	<div
		class="flex flex-col gap-1 p-[22px_24px] w-[220px] bg-[var(--color-paper)] border-l border-[var(--color-border)]"
	>
		<Eyebrow>DAYS TO RACE</Eyebrow>
		<Stat value={daysToRace} size="2xl" />
		<Body size="sm" muted>{blockLabel}</Body>
	</div>
	<div
		class="flex flex-col gap-1 p-[22px_24px] w-[260px] bg-[var(--color-paper)] border-l border-[var(--color-border)]"
	>
		<Eyebrow>GOAL PACE</Eyebrow>
		<Stat value={goalPace} unit="/km" size="2xl" />
		<Body size="sm" muted>{thresholdNote}</Body>
	</div>
</div>
