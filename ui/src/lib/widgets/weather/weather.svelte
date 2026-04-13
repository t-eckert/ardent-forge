<script lang="ts">
	import type { WeatherPayload } from '$lib/schemas/widgets/weather';
	import { CloudSun } from '$lib/icons';

	interface Props {
		payload: WeatherPayload;
	}

	let { payload }: Props = $props();
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
		<div class="flex items-baseline gap-1.5">
			<span class="font-mono text-[44px] leading-none">{payload.currentC}</span>
			<span class="font-mono text-[16px] opacity-85">°C</span>
		</div>
		<div class="flex gap-5 font-mono text-[11px]">
			{#each payload.hours as h, i (h.label)}
				<div class="flex flex-col gap-0.5 items-center" class:opacity-85={i !== 2}>
					<span>{h.label}</span>
					<span class="text-[14px]">{h.tempC}°</span>
				</div>
			{/each}
		</div>
	</div>
	<div class="px-5 pb-4 text-[13px] opacity-90">{payload.summary}</div>
</article>
