<script lang="ts">
	import { AgentsRoster } from '$lib/library';
	import { makeAgentRunList } from '$lib/mocks';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

<AgentsRoster agents={data.agents} recentRuns={makeAgentRunList()} />
