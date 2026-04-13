<script lang="ts">
	import { page } from '$app/state';
	import { ThreadView } from '$lib/threads';
	import { makeThreadList, makeRenameThread } from '$lib/mocks';
	import { Display, Body } from '$lib/typography';

	const rename = makeRenameThread();
	const threads = [rename, ...makeThreadList()];
	const active = $derived(page.params.id === rename.id ? rename : null);
</script>

{#if active}
	<ThreadView {threads} {active} />
{:else}
	<div class="p-12 flex flex-col gap-3">
		<Display size="md">Thread not found</Display>
		<Body muted>No mock thread has id <span class="font-mono">{page.params.id}</span>.</Body>
	</div>
{/if}
