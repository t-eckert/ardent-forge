<script lang="ts">
	import { ThreadsView } from '$lib/threads';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

<ThreadsView threads={data.threads} />
