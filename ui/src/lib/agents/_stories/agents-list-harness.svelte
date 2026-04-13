<script lang="ts">
	import AgentsListView from '../views/agents-list-view.svelte';
	import { makeAgentRunList } from '$lib/mocks';

	const runs = makeAgentRunList();
</script>

<div class="min-h-screen bg-[var(--color-paper)]">
	<AgentsListView {runs} />
</div>
