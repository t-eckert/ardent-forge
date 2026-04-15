<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import type { Thread, ThreadDetail } from '$lib/schemas/thread';
	import { api } from '$lib/api/typed';
	import ThreadList from '../components/thread-list.svelte';
	import Conversation from '../components/conversation.svelte';
	import ThreadComposer from '../components/thread-composer.svelte';

	interface Props {
		threads: Thread[];
		active: ThreadDetail;
	}

	let { threads, active }: Props = $props();

	/** True iff any dispatched card on this thread is still waiting on the
	 *  coordinator. When true, we poll so the stage indicator and resolution
	 *  message appear without a manual refresh. */
	const hasPendingTasks = $derived.by(() => {
		for (const m of active.messages) {
			if (m.role !== 'assistant') continue;
			if (m.variant !== 'task-dispatched') continue;
			const status = m.dispatchedTask?.status;
			if (status && status !== 'done' && status !== 'failed') return true;
		}
		return false;
	});

	$effect(() => {
		if (!hasPendingTasks) return;
		const id = setInterval(() => {
			invalidateAll();
		}, 10_000);
		return () => clearInterval(id);
	});

	async function onsubmit(content: string) {
		// Fire-and-consume the streaming response so the assistant message is
		// fully persisted server-side before we refetch. The loader then
		// picks up both the user message and the assistant reply.
		const res = await api.chat.send(content, active.id);
		if (res.body) {
			const reader = res.body.getReader();
			while (true) {
				const { done } = await reader.read();
				if (done) break;
			}
		}
		await invalidateAll();
	}
</script>

<div class="flex min-h-[calc(100vh-3rem)]">
	<ThreadList {threads} activeId={active.id} />
	<div class="flex flex-col flex-1 min-w-0">
		<Conversation messages={active.messages} />
		<ThreadComposer
			placeholder={'Continue the thread — e.g. "ship the PR"'}
			{onsubmit}
		/>
	</div>
</div>
