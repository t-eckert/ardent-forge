<script lang="ts">
	import TaskListView from '../views/task-list-view.svelte';
	import { makeTaskList } from '$lib/mocks';

	const tasks = makeTaskList();
</script>

<div class="min-h-screen bg-[var(--color-paper)]">
	<TaskListView {tasks} />
</div>
