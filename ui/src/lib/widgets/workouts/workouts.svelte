<script lang="ts">
	import type { WorkoutsPayload } from '$lib/schemas/widgets/workouts';
	import WidgetShell from '../components/widget-shell.svelte';
	import { Heartbeat } from '$lib/icons';
	import { Meta, Stat, Eyebrow } from '$lib/typography';
	import { Chip } from '$lib/components';

	interface Props {
		payload: WorkoutsPayload;
	}
	let { payload }: Props = $props();
</script>

<WidgetShell
	toolId="health.workouts"
	badgeIcon={Heartbeat}
	badgeTone="ember"
	context={'block: ' + payload.blockLabel}
	footerMeta={payload.sourcesLine}
>
	{#snippet headerMeta()}
		<Meta tone="moss">● on track</Meta>
	{/snippet}

	{#snippet body()}
		<div class="grid grid-cols-4 gap-8 px-5 py-4 border-b border-[var(--color-border)]">
			<div class="flex flex-col gap-1">
				<Eyebrow>GOAL</Eyebrow>
				<span class="font-display text-[20px] text-[var(--color-ink)]">{payload.goal}</span>
				<Meta size="xs">{payload.daysToEvent} days · {payload.eventLabel}</Meta>
			</div>
			<div class="flex flex-col gap-1">
				<Eyebrow>WEEK VOLUME</Eyebrow>
				<div class="flex items-baseline gap-1.5">
					<Stat value={payload.weekVolumeLabel} size="md" />
					{#if payload.weekVolumeDelta}<Meta tone="moss">{payload.weekVolumeDelta}</Meta>{/if}
				</div>
			</div>
			<div class="flex flex-col gap-1">
				<Eyebrow>LONG RUN</Eyebrow>
				<Stat value={payload.longRunLabel} size="md" />
			</div>
			<div class="flex flex-col gap-1">
				<Eyebrow>THRESHOLD</Eyebrow>
				<div class="flex items-baseline gap-1.5">
					<Stat value={payload.thresholdPaceLabel} size="md" />
					{#if payload.thresholdPaceDelta}<Meta tone="ember">{payload.thresholdPaceDelta}</Meta>{/if}
				</div>
			</div>
		</div>

		<div class="flex flex-col gap-2.5 px-5 py-4">
			<div class="flex items-center justify-between">
				<Eyebrow>RECENT SESSIONS</Eyebrow>
				<a href="/library/fields/health" class="font-mono text-[10px] text-[var(--color-ember-deep)]"
					>view all →</a
				>
			</div>
			{#each payload.recent as r, i (i)}
				<div
					class="grid grid-cols-[70px_1fr_140px_110px_76px] items-center py-1.5 text-[13px]"
					class:border-b={i < payload.recent.length - 1}
					style={i < payload.recent.length - 1 ? 'border-color: var(--color-border)' : ''}
				>
					<span class="font-mono text-[12px] text-[var(--color-graphite)]">{r.dateLabel}</span>
					<span class="text-[var(--color-ink)]">{r.title}</span>
					<span class="font-mono text-[12px]">{r.volumeLabel}</span>
					<span class="text-[var(--color-slate)] text-[12px]">{r.intensityLabel}</span>
					<Chip tone={r.source === 'strava' ? 'ember' : 'neutral'}>{r.source}</Chip>
				</div>
			{/each}
		</div>
	{/snippet}
</WidgetShell>
