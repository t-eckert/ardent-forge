<script lang="ts">
	import { page } from '$app/state';
	import { ThreadView, ThreadsView } from '$lib/threads';
	import { Display, Body } from '$lib/typography';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();

	const initialMessage = $derived(
		new URLSearchParams(window.location.search).get('send') ?? undefined
	);
</script>

{#if data.active}
	<ThreadView threads={data.threads} active={data.active} {initialMessage} />
{:else if data.threads.length}
	<ThreadsView threads={data.threads} />
{:else}
	<div class="p-12 flex flex-col gap-3">
		<Display size="md">Thread not found</Display>
		<Body muted>No thread with id <span class="font-mono">{page.params.id}</span>.</Body>
	</div>
{/if}
