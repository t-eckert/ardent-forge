<script lang="ts">
	import type { Task } from '$lib/schemas/task';
	import { Display, Meta, Eyebrow } from '$lib/typography';
	import { Chip } from '$lib/components';
	import { formatTime } from '$lib/utils/date';

	interface Props {
		task: Task;
	}

	let { task }: Props = $props();
</script>

<header class="flex flex-col gap-2 px-10 pt-10 pb-6 border-b border-[var(--color-border)]">
	<Eyebrow>TASK · {task.type.toUpperCase()} · {task.id}</Eyebrow>
	<div class="flex items-start justify-between gap-6">
		<Display size="md">{task.title || task.description.slice(0, 120)}</Display>
		<Chip tone={task.status === 'completed' ? 'moss' : task.status === 'failed' ? 'ember' : 'ember'}>
			{task.status}
		</Chip>
	</div>
	<Meta size="sm">
		from {task.source}
		{#if task.origin_thread_id} · thread <a href="/threads/{task.origin_thread_id}" class="underline">{task.origin_thread_id.slice(0, 8)}</a>{/if}
		 · created {formatTime(task.created_at)}
		{#if task.completed_at} · completed {formatTime(task.completed_at)}{/if}
	</Meta>
</header>
