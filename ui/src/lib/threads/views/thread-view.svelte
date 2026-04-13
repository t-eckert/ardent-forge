<script lang="ts">
	import type { Thread, ThreadDetail } from '$lib/schemas/thread';
	import ThreadList from '../components/thread-list.svelte';
	import Conversation from '../components/conversation.svelte';
	import ThreadComposer from '../components/thread-composer.svelte';

	interface Props {
		threads: Thread[];
		active: ThreadDetail;
	}

	let { threads, active }: Props = $props();
</script>

<div class="flex min-h-[calc(100vh-3rem)]">
	<ThreadList {threads} activeId={active.id} />
	<div class="flex flex-col flex-1 min-w-0">
		<Conversation messages={active.messages} />
		<ThreadComposer placeholder={'Continue the thread — e.g. "ship the PR"'} />
	</div>
</div>
