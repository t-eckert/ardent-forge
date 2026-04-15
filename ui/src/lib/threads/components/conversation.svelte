<script lang="ts">
	import type { Message } from '$lib/schemas/thread';
	import UserMessage from './user-message.svelte';
	import AssistantMessage from './assistant-message.svelte';

	interface Props {
		messages: Message[];
		streamingText?: string;
	}

	let { messages, streamingText }: Props = $props();

	let container: HTMLDivElement | undefined = $state();

	function scrollToBottom() {
		if (container) {
			container.scrollTop = container.scrollHeight;
		}
	}

	// Scroll when messages change or streaming text updates.
	$effect(() => {
		// Touch reactive deps.
		messages.length;
		streamingText;
		scrollToBottom();
	});
</script>

<div bind:this={container} class="flex flex-col gap-7 px-12 py-8 overflow-y-auto flex-1">
	{#each messages as message (message.id)}
		{#if message.role === 'user'}
			<UserMessage {message} />
		{:else}
			<AssistantMessage {message} />
		{/if}
	{/each}
</div>
