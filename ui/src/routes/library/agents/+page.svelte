<script lang="ts">
	import { AgentsRoster } from '$lib/library';
	import { makeAgentRunList } from '$lib/mocks';

	// Static roster stand-in — Phase M swaps this for /api/agents.
	const agents = [
		{ name: 'code-agent', task_type: 'code', stages: ['triage', 'execute', 'verify', 'deliver'], connectors: ['github'] },
		{ name: 'plan', task_type: 'plan', stages: ['triage', 'execute', 'verify', 'deliver'], connectors: ['github'] },
		{ name: 'research', task_type: 'research', stages: ['triage', 'execute', 'verify', 'deliver'], connectors: ['notebook'] },
		{ name: 'tickets', task_type: 'tickets', stages: ['triage', 'execute', 'verify', 'deliver'], connectors: ['linear'] },
		{ name: 'echo', task_type: 'echo', stages: ['execute'], connectors: [] }
	];
</script>

<AgentsRoster {agents} recentRuns={makeAgentRunList()} />
