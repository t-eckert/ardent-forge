<script lang="ts">
	import { page } from '$app/state';
	import { TaskDetailView, TaskListView } from '$lib/tasks';
	import { Display, Body } from '$lib/typography';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

{#if data.active}
	<TaskDetailView tasks={data.tasks} active={data.active} />
{:else if data.tasks.length}
	<TaskListView tasks={data.tasks} />
{:else}
	<div class="p-12 flex flex-col gap-3">
		<Display size="md">Task not found</Display>
		<Body muted>No task with id <span class="font-mono">{page.params.id}</span>.</Body>
	</div>
{/if}
