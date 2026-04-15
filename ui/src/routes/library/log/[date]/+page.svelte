<script lang="ts">
	import { Display, Eyebrow, Body } from '$lib/typography';
	import Markdown from '$lib/components/markdown.svelte';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();

	function dayLabel(iso: string): string {
		try {
			return new Date(iso + 'T12:00:00').toLocaleDateString('en-US', {
				weekday: 'long',
				month: 'long',
				day: 'numeric',
				year: 'numeric'
			});
		} catch {
			return iso;
		}
	}
</script>

<div class="flex flex-col gap-6 px-14 py-9 max-w-[860px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<a href="/library/log" class="font-mono text-[11px] text-[var(--color-ember-deep)]">
			← Daily log
		</a>
		<Eyebrow>LOG · {data.date}</Eyebrow>
		<Display size="lg">{dayLabel(data.date)}</Display>
	</div>

	{#if data.body}
		<Markdown source={data.body} />
	{:else}
		<Body muted>No log entry found for {data.date}.</Body>
	{/if}
</div>
