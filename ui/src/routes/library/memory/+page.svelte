<script lang="ts">
	import { MemoryLibrary } from '$lib/library';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

<MemoryLibrary entries={data.entries} />
