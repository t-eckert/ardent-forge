<script lang="ts">
	import { page } from '$app/state';
	import { RunDetailView } from '$lib/agents';
	import { makeAgentRunList, makeCodeAgentRunDetail, makeCodeDiff } from '$lib/mocks';
	import { Display, Body } from '$lib/typography';

	const runs = makeAgentRunList();
	const codeAgentRun = makeCodeAgentRunDetail();
	const artifact = makeCodeDiff();

	const active = $derived(
		page.params.agent === codeAgentRun.kind && page.params.run === codeAgentRun.id
			? codeAgentRun
			: null
	);
</script>

{#if active}
	<RunDetailView {runs} {active} {artifact} />
{:else}
	<div class="p-12 flex flex-col gap-3">
		<Display size="md">Run not found</Display>
		<Body muted>
			No mock run at <span class="font-mono">/agents/{page.params.agent}/{page.params.run}</span>.
		</Body>
	</div>
{/if}
