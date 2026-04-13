<script lang="ts">
	import type { AgentRun, AgentRunDetail } from '$lib/schemas/agent';
	import type { WidgetPayload } from '$lib/schemas/widgets';
	import AgentList from '../components/agent-list.svelte';
	import RunHeader from '../components/run-header.svelte';
	import RunMetaStrip from '../components/run-meta-strip.svelte';
	import RunTimeline from '../components/run-timeline.svelte';
	import RunArtifact from '../components/run-artifact.svelte';

	interface Props {
		runs: AgentRun[];
		active: AgentRunDetail;
		artifact?: WidgetPayload;
	}

	let { runs, active, artifact }: Props = $props();
</script>

<div class="flex min-h-[calc(100vh-3rem)]">
	<AgentList {runs} activeId={active.id} />
	<div class="flex flex-col flex-1 min-w-0 px-10 py-7 gap-6">
		<RunHeader run={active} />
		<RunMetaStrip metas={active.metas} />
		<RunTimeline steps={active.steps} />
		{#if artifact && active.artifactLabel}
			<RunArtifact label={active.artifactLabel} payload={artifact} />
		{/if}
	</div>
</div>
