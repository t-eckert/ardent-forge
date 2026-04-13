<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import type { PlacesMapPayload } from '$lib/schemas/widgets/places-map';
	import WidgetShell from '../components/widget-shell.svelte';
	import { MapPin } from '$lib/icons';
	import { Meta, Eyebrow, Stat } from '$lib/typography';
	import { Button, Chip } from '$lib/components';

	interface Props {
		payload: PlacesMapPayload;
	}

	let { payload }: Props = $props();

	let mapEl: HTMLDivElement | undefined = $state();
	let mapInstance: import('leaflet').Map | null = null;

	onMount(async () => {
		if (!browser || !mapEl) return;
		const L = (await import('leaflet')).default;
		await import('leaflet/dist/leaflet.css');

		mapInstance = L.map(mapEl, {
			zoomControl: false,
			attributionControl: true,
			scrollWheelZoom: false
		}).setView([payload.centre.lat, payload.centre.lng], payload.zoom);

		L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
			attribution: '© OpenStreetMap',
			maxZoom: 19
		}).addTo(mapInstance);

		payload.results.forEach((place, i) => {
			const active = i === 0;
			const icon = L.divIcon({
				className: 'af-pin',
				html: `<span style="display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;background:${active ? '#E34E18' : '#1A1714'};color:#FAF7F1;font-family:'JetBrains Mono',monospace;font-size:12px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);box-shadow:0 2px 6px rgba(26,23,20,0.25);"><span style="transform:rotate(45deg);">${i + 1}</span></span>`,
				iconSize: [28, 28],
				iconAnchor: [14, 28]
			});
			L.marker([place.coord.lat, place.coord.lng], { icon })
				.addTo(mapInstance!)
				.bindTooltip(place.name, { direction: 'top', offset: [0, -24] });
		});
	});

	onDestroy(() => {
		mapInstance?.remove();
		mapInstance = null;
	});
</script>

<WidgetShell
	toolId="places.map"
	badgeIcon={MapPin}
	badgeTone="signal"
	context={payload.query}
	footerMeta="source: osm · places · cached 3m"
>
	{#snippet headerMeta()}
		<Meta size="xs">{payload.results.length} results</Meta>
	{/snippet}

	{#snippet body()}
		<div class="flex min-h-[420px]">
			<div class="flex-1 relative">
				<div bind:this={mapEl} class="w-full h-full" style="min-height: 420px;"></div>
				{#if !browser}
					<!-- Storybook CSR still hits this block briefly before onMount -->
					<div class="absolute inset-0 flex items-center justify-center bg-[var(--color-bench)]">
						<Meta size="xs">loading map…</Meta>
					</div>
				{/if}
			</div>

			<div class="flex flex-col w-[340px] border-l border-[var(--color-border)]">
				<div class="px-3.5 py-2.5 border-b border-[var(--color-border)]">
					<Eyebrow>RESULTS · sorted by distance</Eyebrow>
				</div>
				{#each payload.results as place, i (place.id)}
					<div
						class="flex gap-3 p-3.5"
						style={i === 0 ? 'background: var(--color-bench);' : ''}
						class:border-b={i < payload.results.length - 1}
					>
						<div class="flex-shrink-0 pt-0.5">
							<span
								class="inline-flex items-center justify-center w-[22px] h-[22px] rounded-full rounded-bl-none font-mono text-[11px] text-[var(--color-paper)] -rotate-45"
								style="background: {i === 0 ? 'var(--color-ember)' : 'var(--color-ink)'};"
							>
								<span class="rotate-45">{i + 1}</span>
							</span>
						</div>
						<div class="flex flex-col gap-1 flex-1 min-w-0">
							<div class="flex items-baseline justify-between gap-2">
								<span class="text-[14px] font-medium text-[var(--color-ink)]">{place.name}</span>
								<Stat value="{place.distanceLabel} · {place.etaLabel}" size="xs" />
							</div>
							{#if place.neighbourhood || place.descriptor}
								<Meta size="xs">
									{[place.neighbourhood, place.descriptor].filter(Boolean).join(' · ')}
								</Meta>
							{/if}
							<div class="flex gap-1 pt-0.5 flex-wrap">
								{#each place.tags as tag (tag)}
									<Chip tone="outline">{tag}</Chip>
								{/each}
								{#if place.rating}
									<Chip tone="moss">{place.rating}</Chip>
								{/if}
							</div>
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/snippet}

	{#snippet actions()}
		<Button variant="secondary" size="sm">Expand</Button>
		<Button variant="secondary" size="sm">Directions</Button>
		<Button variant="primary" size="sm">Order from {payload.results[0].name}</Button>
	{/snippet}
</WidgetShell>
