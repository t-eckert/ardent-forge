<script lang="ts">
	import { TaskListView, DispatchForm } from '$lib/tasks';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

<div class="flex flex-col gap-7 px-14 pt-9 max-w-[1440px] mx-auto">
	<DispatchForm repos={data.repos ?? []} />
	<TaskListView tasks={data.tasks} />
</div>
