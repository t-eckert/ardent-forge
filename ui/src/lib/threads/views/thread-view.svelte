<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import type { Thread, ThreadDetail, Message, UserMessage, AssistantMessage } from '$lib/schemas/thread';
	import { api } from '$lib/api/typed';
	import ThreadList from '../components/thread-list.svelte';
	import Conversation from '../components/conversation.svelte';
	import ThreadComposer from '../components/thread-composer.svelte';

	interface Props {
		threads: Thread[];
		active: ThreadDetail;
		initialMessage?: string;
	}

	let { threads, active, initialMessage }: Props = $props();

	// Local messages includes server-persisted messages + any optimistic additions.
	let optimistic: Message[] = $state([]);
	let streamingText = $state('');

	// Merge server messages with optimistic ones. Clear optimistic on server refresh.
	const allMessages = $derived.by(() => {
		if (optimistic.length === 0) return active.messages;
		return [...active.messages, ...optimistic];
	});

	// Clear optimistic messages when the server data refreshes (after invalidateAll).
	$effect(() => {
		// When active.messages changes (new data from server), drop optimistic.
		active.messages;
		optimistic = [];
		streamingText = '';
	});

	/** True iff any dispatched card on this thread is still waiting on the
	 *  coordinator. When true, we poll so the stage indicator and resolution
	 *  message appear without a manual refresh. */
	const hasPendingTasks = $derived.by(() => {
		for (const m of allMessages) {
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

	// Auto-send a message passed from the Today composer (via ?send= query param).
	let autoSent = false;
	$effect(() => {
		if (initialMessage && !autoSent) {
			autoSent = true;
			// Clean the URL so a refresh doesn't re-send.
			const url = new URL(window.location.href);
			url.searchParams.delete('send');
			window.history.replaceState({}, '', url.toString());
			onsubmit(initialMessage);
		}
	});

	async function onsubmit(content: string) {
		const now = new Date().toISOString();

		// Optimistic user message.
		const userMsg: UserMessage = {
			role: 'user',
			id: `opt-user-${Date.now()}`,
			iso: now,
			content
		};

		// Provisional assistant message that will accumulate streamed text.
		const assistantMsg: AssistantMessage = {
			role: 'assistant',
			id: `opt-assistant-${Date.now()}`,
			iso: now,
			toolProfile: 'FORGE',
			variant: 'text',
			text: '',
			widgets: []
		};

		optimistic = [userMsg, assistantMsg];
		streamingText = '';

		const res = await api.chat.send(content, active.id);
		if (res.body) {
			const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
			while (true) {
				const { done, value } = await reader.read();
				if (done) break;
				streamingText += value;
				// Update the provisional assistant message text reactively.
				assistantMsg.text = streamingText;
				optimistic = [userMsg, assistantMsg];
			}
		}

		// Sync with server state — picks up widgets, task-dispatched cards, etc.
		await invalidateAll();
	}
</script>

<div class="flex min-h-[calc(100vh-3rem)]">
	<ThreadList {threads} activeId={active.id} />
	<div class="flex flex-col flex-1 min-w-0">
		<Conversation messages={allMessages} {streamingText} />
		<ThreadComposer
			placeholder={'Message Forge…'}
			{onsubmit}
		/>
	</div>
</div>
