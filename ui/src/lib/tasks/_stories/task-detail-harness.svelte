<script lang="ts">
	import TaskDetailView from '../views/task-detail-view.svelte';
	import { makeTaskList } from '$lib/mocks';
	import type { Task } from '$lib/schemas/task';

	interface Props {
		activeId?: string;
	}
	let { activeId = '01KP000000000000000000RSRC' }: Props = $props();

	const tasks = makeTaskList();
	const active = $derived<Task>(tasks.find((t) => t.id === activeId) ?? tasks[0]);
</script>

<div class="min-h-screen bg-[var(--color-paper)]">
	<TaskDetailView {tasks} {active} />
</div>
