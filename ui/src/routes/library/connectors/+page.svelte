<script lang="ts">
	import { ConnectorsRoster } from '$lib/library';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

<ConnectorsRoster connectors={data.connectors} />
