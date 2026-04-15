<script lang="ts">
	import type { AssistantMessage } from '$lib/schemas/thread';
	import { Meta } from '$lib/typography';
	import Markdown from '$lib/components/markdown.svelte';
	import { WidgetHost } from '$lib/widgets';
	import { formatTime } from '$lib/utils/date';
	import TaskDispatchedCard from './task-dispatched-card.svelte';
	import TaskResolvedMessage from './task-resolved-message.svelte';
	import MemorySavedChip from './memory-saved-chip.svelte';

	interface Props {
		message: AssistantMessage;
	}

	let { message }: Props = $props();
</script>

<div class="flex flex-col gap-3 max-w-[820px]">
	<header class="flex items-center gap-2.5">
		<span class="inline-block w-[22px] h-[22px] bg-[var(--color-ember)] rounded-full"></span>
		<Meta size="sm">FORGE · {message.toolProfile} · {formatTime(message.iso)}</Meta>
	</header>

	{#if message.text}
		<Markdown source={message.text} />
	{/if}

	{#if message.variant === 'widget'}
		{#each message.widgets as widget, i (i)}
			<WidgetHost payload={widget} />
		{/each}
	{:else if message.variant === 'task-dispatched' && message.dispatchedTask}
		<TaskDispatchedCard task={message.dispatchedTask} />
	{:else if message.variant === 'task-resolved' && message.resolvedTask}
		<TaskResolvedMessage task={message.resolvedTask} narration={message.text} />
	{:else if message.variant === 'memory-saved' && message.savedMemory}
		<MemorySavedChip memory={message.savedMemory} />
	{/if}
</div>
