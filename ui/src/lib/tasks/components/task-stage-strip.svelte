<script lang="ts">
	import type { Task } from '$lib/schemas/task';
	import { Meta } from '$lib/typography';

	interface Props {
		task: Task;
	}

	let { task }: Props = $props();

	const stages = ['queued', 'triaging', 'executing', 'verifying', 'delivering', 'completed'] as const;

	const activeIdx = $derived(
		task.status === 'failed' ? -1 : stages.indexOf(task.status as (typeof stages)[number])
	);
</script>

<div class="flex gap-3 px-10 py-5 border-b border-[var(--color-border)]">
	{#each stages as stage, i (stage)}
		{@const done = activeIdx > i || task.status === 'completed'}
		{@const active = activeIdx === i && task.status !== 'completed'}
		<div class="flex flex-col gap-1 min-w-0">
			<div
				class="h-[2px] w-16"
				style="background: {done ? 'var(--color-moss)' : active ? 'var(--color-ember)' : 'var(--color-border)'}"
			></div>
			<Meta size="sm">{stage}</Meta>
		</div>
	{/each}
</div>
