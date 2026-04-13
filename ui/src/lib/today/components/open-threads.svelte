<script lang="ts">
	import type { Thread } from '$lib/schemas/thread';
	import { Heading, Meta } from '$lib/typography';
	import { StatusDot } from '$lib/components';
	import { formatRelative, formatTime } from '$lib/utils/date';

	interface Props {
		threads: Thread[];
	}

	let { threads }: Props = $props();

	const unreadCount = $derived(threads.filter((t) => t.unread).length);

	function stamp(iso: string): string {
		const ageHours = (Date.now() - new Date(iso).getTime()) / 3_600_000;
		if (ageHours < 20) return formatTime(iso);
		if (ageHours < 44) return "y'day";
		return formatRelative(iso);
	}
</script>

<section class="flex flex-col gap-2.5">
	<header class="flex items-end justify-between pb-1.5 border-b border-[var(--color-border)]">
		<div class="flex items-baseline gap-2.5">
			<Heading size="md">Open threads</Heading>
			<Meta size="sm">{threads.length} · {unreadCount} UNREAD</Meta>
		</div>
		<a href="/threads" class="font-mono text-[11px] text-[var(--color-ember-deep)]">threads →</a>
	</header>
	<div class="flex flex-col">
		{#each threads as thread, i (thread.id)}
			<a
				href="/threads/{thread.id}"
				class="flex items-start gap-2.5 py-2.5"
				class:border-b={i < threads.length - 1}
				style={i < threads.length - 1 ? 'border-color: var(--color-border)' : ''}
			>
				<StatusDot tone={thread.unread ? 'ember' : 'stone'} class="mt-1.5 flex-shrink-0" />
				<div class="flex flex-col gap-0.5 flex-1 min-w-0">
					<span class="text-[13px] font-medium text-[var(--color-ink)] truncate">
						{thread.title}
					</span>
					<Meta size="xs">{thread.preview}</Meta>
				</div>
				<Meta size="xs">{stamp(thread.lastActivityIso)}</Meta>
			</a>
		{/each}
	</div>
</section>
