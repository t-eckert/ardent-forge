<script lang="ts">
	import type { Thread } from '$lib/schemas/thread';
	import { Chip, StatusDot } from '$lib/components';
	import { Meta } from '$lib/typography';
	import { formatRelative, formatTime } from '$lib/utils/date';

	interface Props {
		thread: Thread;
		active?: boolean;
	}

	let { thread, active = false }: Props = $props();

	const kindTone = $derived(thread.kind === 'code+tools' ? 'ember' : 'ember');

	function stamp(iso: string): string {
		const ageHours = (Date.now() - new Date(iso).getTime()) / 3_600_000;
		if (ageHours < 20) return formatTime(iso);
		if (ageHours < 44) return "y'day";
		return formatRelative(iso);
	}
</script>

<a
	href="/threads/{thread.id}"
	class="flex flex-col gap-1 px-5 py-3 border-b border-[var(--color-border)] transition-colors"
	class:bg-bench={active}
	style={active
		? 'background: var(--color-bench); border-left: 2px solid var(--color-ember);'
		: ''}
>
	<div class="flex items-center justify-between gap-2">
		<div class="flex items-center gap-1.5 min-w-0">
			{#if thread.unread}<StatusDot tone="ember" />{/if}
			<span
				class="text-[13px] truncate"
				class:font-medium={thread.unread || active}
				class:text-ink={thread.unread || active}
				style={thread.unread || active ? 'color: var(--color-ink)' : 'color: var(--color-slate)'}
			>
				{thread.title}
			</span>
		</div>
		<Meta size="xs">{stamp(thread.lastActivityIso)}</Meta>
	</div>
	<Meta size="xs">{thread.preview}</Meta>
	{#if active || thread.widgetCount > 0}
		<div class="flex gap-1 pt-0.5">
			{#if active}<Chip tone={kindTone}>{thread.kind}</Chip>{/if}
			{#if thread.widgetCount > 0}<Chip tone="outline">{thread.widgetCount} widgets</Chip>{/if}
		</div>
	{/if}
</a>
