<script lang="ts">
	import type { WeatherPayload } from '$lib/schemas/widgets/weather';
	import { CloudSun } from '$lib/icons';

	interface Props {
		payload: WeatherPayload;
	}

	let { payload }: Props = $props();

	/** Abbreviate "2026-04-15" → "Tue" */
	function dayLabel(iso: string): string {
		try {
			return new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short' });
		} catch {
			return iso.slice(5);
		}
	}
</script>

<article
	class="flex flex-col max-w-[720px] rounded-[8px] overflow-hidden text-[var(--color-paper)]"
	style="background: linear-gradient(135deg, #E34E18 0%, #C73D0F 100%);"
>
	<header class="flex items-center justify-between px-5 py-3 border-b border-white/15">
		<div class="flex items-center gap-2.5">
			<CloudSun size={14} weight="regular" />
			<span class="font-mono text-[11px] tracking-[0.1em] opacity-90"
				>WEATHER.FORECAST · {payload.location.toUpperCase()}</span
			>
		</div>
		<span class="font-mono text-[10px] opacity-85">{payload.asOf}</span>
	</header>
	<div class="flex items-end justify-between px-5 py-4">
		<div class="flex flex-col gap-1">
			<div class="flex items-baseline gap-1.5">
				<span class="font-mono text-[44px] leading-none">{payload.currentC}</span>
				<span class="font-mono text-[16px] opacity-85">°C</span>
			</div>
			<span class="text-[13px] opacity-90">{payload.summary}</span>
		</div>
		<div class="flex gap-4 font-mono text-[11px]">
			{#each payload.daily.slice(0, 6) as d (d.date)}
				<div class="flex flex-col gap-0.5 items-center">
					<span class="opacity-75">{dayLabel(d.date)}</span>
					<span class="text-[13px]">{d.maxC}°</span>
					<span class="text-[11px] opacity-65">{d.minC}°</span>
				</div>
			{/each}
		</div>
	</div>
</article>
