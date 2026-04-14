<script lang="ts">
	import { page } from '$app/state';
	import { RunDetailView } from '$lib/agents';
	import { makeAgentRunList, makeCodeAgentRunDetail, makeCodeDiff } from '$lib/mocks';
	import { Display, Body } from '$lib/typography';

	// Phase J will replace this stand-in with a first-class TaskDetailView
	// that reads /api/tasks/[id] + the origin-thread breadcrumb.
	const runs = makeAgentRunList();
	const codeAgentRun = makeCodeAgentRunDetail();
	const artifact = makeCodeDiff();

	const active = $derived(page.params.id === codeAgentRun.id ? codeAgentRun : null);
</script>

{#if active}
	<RunDetailView {runs} {active} {artifact} />
{:else}
	<div class="p-12 flex flex-col gap-3">
		<Display size="md">Task not found</Display>
		<Body muted>No mock task with id <span class="font-mono">{page.params.id}</span>.</Body>
	</div>
{/if}
