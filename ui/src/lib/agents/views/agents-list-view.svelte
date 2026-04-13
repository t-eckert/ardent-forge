<script lang="ts">
	import type { AgentRun } from '$lib/schemas/agent';
	import AgentList from '../components/agent-list.svelte';
	import { Display, Body } from '$lib/typography';
	import { EmptyState } from '$lib/components';

	interface Props {
		runs: AgentRun[];
	}

	let { runs }: Props = $props();
</script>

<div class="flex min-h-[calc(100vh-3rem)]">
	<AgentList {runs} />
	<div class="flex flex-col flex-1 items-center justify-center gap-4 p-12 min-w-0">
		<Display size="md">Pick a run</Display>
		<Body muted>Select a run from the list to see its timeline and artifacts.</Body>
		<EmptyState message="⌘K TO JUMP TO A RUN BY ID" />
	</div>
</div>
