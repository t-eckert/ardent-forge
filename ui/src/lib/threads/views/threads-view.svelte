<script lang="ts">
	import type { Thread } from '$lib/schemas/thread';
	import ThreadList from '../components/thread-list.svelte';
	import { Display, Body } from '$lib/typography';
	import { EmptyState } from '$lib/components';

	interface Props {
		threads: Thread[];
	}

	let { threads }: Props = $props();
</script>

<div class="flex min-h-[calc(100vh-3rem)]">
	<ThreadList {threads} />
	<div class="flex flex-col flex-1 items-center justify-center gap-4 p-12 min-w-0">
		<Display size="md">Pick a thread</Display>
		<Body muted>
			Select a conversation from the list, or press <span class="font-mono">⌘N</span> to start a new one.
		</Body>
		<EmptyState message="⌘K TO FIND A THREAD BY NAME" />
	</div>
</div>
