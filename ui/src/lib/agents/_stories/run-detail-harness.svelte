<script lang="ts">
	import RunDetailView from '../views/run-detail-view.svelte';
	import { makeAgentRunList, makeCodeAgentRunDetail, makeCodeDiff } from '$lib/mocks';

	const runs = makeAgentRunList();
	const active = makeCodeAgentRunDetail();
	const artifact = makeCodeDiff();
</script>

<div class="min-h-screen bg-[var(--color-paper)]">
	<RunDetailView {runs} {active} {artifact} />
</div>
