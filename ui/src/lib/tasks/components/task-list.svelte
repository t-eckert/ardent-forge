<script lang="ts">
	import type { Task } from '$lib/schemas/task';
	import TaskRow from './task-row.svelte';
	import { Eyebrow, Heading } from '$lib/typography';
	import { Chip } from '$lib/components';

	interface Props {
		tasks: Task[];
		activeId?: string;
	}

	let { tasks, activeId }: Props = $props();

	type Filter = 'all' | 'active' | 'needs-me' | 'failed';
	let filter = $state<Filter>('all');

	const activeCount = $derived(
		tasks.filter((t) =>
			['queued', 'triaging', 'executing', 'verifying', 'delivering'].includes(t.status)
		).length
	);

	const visible = $derived(
		filter === 'all'
			? tasks
			: filter === 'active'
				? tasks.filter((t) => ['queued', 'triaging', 'executing'].includes(t.status))
				: filter === 'needs-me'
					? tasks.filter((t) => ['verifying', 'delivering'].includes(t.status))
					: tasks.filter((t) => t.status === 'failed')
	);

	const filters: Filter[] = ['all', 'active', 'needs-me', 'failed'];
</script>

<aside class="flex flex-col w-[300px] border-r border-[var(--color-border)] bg-[var(--color-paper)]">
	<header class="flex flex-col gap-1 px-5 pt-[18px] pb-3 border-b border-[var(--color-border)]">
		<Eyebrow>TASKS · {tasks.length} · {activeCount} ACTIVE</Eyebrow>
		<Heading size="md">Queue</Heading>
	</header>
	<div class="flex gap-1.5 px-4 py-2.5 border-b border-[var(--color-border)]">
		{#each filters as f (f)}
			<button type="button" onclick={() => (filter = f)} class="cursor-pointer" aria-pressed={filter === f}>
				<Chip tone={filter === f ? 'ink' : 'outline'}>{f}</Chip>
			</button>
		{/each}
	</div>
	<div class="flex-1 overflow-y-auto">
		{#each visible as task (task.id)}
			<TaskRow {task} active={task.id === activeId} />
		{/each}
	</div>
</aside>
