<script lang="ts">
	import type { AssistantMessage } from '$lib/schemas/thread';
	import { Meta, Body } from '$lib/typography';
	import { WidgetHost } from '$lib/widgets';
	import { formatTime } from '$lib/utils/date';

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
		<Body>{message.text}</Body>
	{/if}
	{#each message.widgets as widget, i (i)}
		<WidgetHost payload={widget} />
	{/each}
</div>
