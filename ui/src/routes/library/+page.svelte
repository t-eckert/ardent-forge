<script lang="ts">
	import { LibraryIndex } from '$lib/library';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

<LibraryIndex
	counts={data.counts}
	agentCount={data.agentCount}
	connectorCount={data.connectorCount}
	memoryCount={data.memoryCount}
/>
