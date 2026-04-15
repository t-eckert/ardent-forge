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
	weather={data.weather}
	runs={data.runs}
	todos={data.todos}
	yesterdayRows={data.yesterdayRows}
/>
