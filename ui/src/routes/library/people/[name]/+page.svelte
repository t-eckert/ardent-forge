<script lang="ts">
	import { Display, Eyebrow, Body } from '$lib/typography';
	import Markdown from '$lib/components/markdown.svelte';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

<div class="flex flex-col gap-6 px-14 py-9 max-w-[860px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<a href="/library/people" class="font-mono text-[11px] text-[var(--color-ember-deep)]">
			← People
		</a>
		<Eyebrow>PEOPLE</Eyebrow>
		<Display size="lg">{data.name}</Display>
	</div>

	{#if data.body}
		<Markdown source={data.body} />
	{:else}
		<Body muted>No page found for {data.name}.</Body>
	{/if}
</div>
