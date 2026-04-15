<script lang="ts">
	import { goto } from '$app/navigation';
	import type { Thread } from '$lib/schemas/thread';
	import { api } from '$lib/api/typed';
	import { adaptThread } from '$lib/api/adapters';
	import ThreadRow from './thread-row.svelte';
	import { Eyebrow, Heading } from '$lib/typography';
	import { Chip } from '$lib/components';
	import { Plus } from '$lib/icons';

	interface Props {
		threads: Thread[];
		activeId?: string;
	}

	let { threads, activeId }: Props = $props();

	async function createThread() {
		const raw = await api.threads.create('New thread');
		const thread = adaptThread(raw);
		await goto(`/threads/${thread.id}`);
	}

	type Filter = 'all' | 'unread' | 'pinned';
	let filter = $state<Filter>('all');

	const visible = $derived(
		filter === 'unread' ? threads.filter((t) => t.unread) : threads
	);
</script>

<aside
	class="flex flex-col w-[320px] border-r border-[var(--color-border)] bg-[var(--color-paper)]"
>
	<header class="flex items-center justify-between px-5 pt-5 pb-3 border-b border-[var(--color-border)]">
		<div class="flex flex-col gap-1">
			<Eyebrow>THREADS · {threads.length}</Eyebrow>
			<Heading size="md">Conversations</Heading>
		</div>
		<button
			type="button"
			onclick={createThread}
			class="flex items-center justify-center w-7 h-7 bg-[var(--color-ink)] text-[var(--color-paper)] rounded-md cursor-pointer"
			aria-label="New thread"
		>
			<Plus size={14} weight="regular" />
		</button>
	</header>

	<div class="flex gap-1.5 px-4 py-2.5 border-b border-[var(--color-border)]">
		{#each ['all', 'unread', 'pinned'] as f (f)}
			<button
				type="button"
				onclick={() => (filter = f as Filter)}
				class="cursor-pointer"
				aria-pressed={filter === f}
			>
				<Chip tone={filter === f ? 'ink' : 'outline'}>{f}</Chip>
			</button>
		{/each}
	</div>

	<div class="flex-1 overflow-y-auto">
		{#each visible as thread (thread.id)}
			<ThreadRow {thread} active={thread.id === activeId} />
		{/each}
	</div>
</aside>
