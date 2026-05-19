<script lang="ts">
	import { TodayView } from '$lib/today';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

<TodayView
	threads={data.threads}
	activeTasks={data.activeTasks}
	queuedTasks={data.queuedTasks}
	recentTasks={data.recentTasks}
	repos={data.repos}
/>
