<script lang="ts">
	// Phase J (Tasks surface) will replace this with the real TasksListView.
	// For now the Agents surface is the best stand-in — it already shows the
	// agent-run flow which is what the Tasks spine is a superset of.
	import { AgentsListView } from '$lib/agents';
	import { makeAgentRunList } from '$lib/mocks';

	const runs = makeAgentRunList();
</script>

<AgentsListView {runs} />
