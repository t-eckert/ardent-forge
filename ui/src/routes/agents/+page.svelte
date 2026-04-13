<script lang="ts">
	import { AgentsListView } from '$lib/agents';
	import { makeAgentRunList } from '$lib/mocks';

	const runs = makeAgentRunList();
</script>

<AgentsListView {runs} />
