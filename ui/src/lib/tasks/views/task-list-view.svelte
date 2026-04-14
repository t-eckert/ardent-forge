<script lang="ts">
	import type { Task } from '$lib/schemas/task';
	import TaskList from '../components/task-list.svelte';
	import { Display, Body } from '$lib/typography';
	import { EmptyState } from '$lib/components';

	interface Props {
		tasks: Task[];
	}

	let { tasks }: Props = $props();
</script>

<div class="flex min-h-[calc(100vh-3rem)]">
	<TaskList {tasks} />
	<div class="flex flex-col flex-1 items-center justify-center gap-4 p-12 min-w-0">
		<Display size="md">Pick a task</Display>
		<Body muted>Select a task to see its stage progression, handler data, and resolution.</Body>
		<EmptyState message="⌘K TO JUMP TO A TASK BY ID" />
	</div>
</div>
