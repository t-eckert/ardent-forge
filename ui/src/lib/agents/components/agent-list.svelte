<script lang="ts">
	import type { AgentRun } from '$lib/schemas/agent';
	import AgentRow from './agent-row.svelte';
	import { Eyebrow, Heading } from '$lib/typography';
	import { Chip } from '$lib/components';

	interface Props {
		runs: AgentRun[];
		activeId?: string;
	}

	let { runs, activeId }: Props = $props();

	type Filter = 'all' | 'active' | 'needs-me' | 'failed';
	let filter = $state<Filter>('all');

	const activeCount = $derived(
		runs.filter((r) => r.status === 'running' || r.status === 'needs-review').length
	);

	const visible = $derived(
		filter === 'all'
			? runs
			: filter === 'active'
				? runs.filter((r) => r.status === 'running' || r.status === 'watching' || r.status === 'cron')
				: filter === 'needs-me'
					? runs.filter((r) => r.status === 'needs-review')
					: runs.filter((r) => r.status === 'failed')
	);

	const filters: Filter[] = ['all', 'active', 'needs-me', 'failed'];
</script>

<aside
	class="flex flex-col w-[300px] border-r border-[var(--color-border)] bg-[var(--color-paper)]"
>
	<header class="flex flex-col gap-1 px-5 pt-[18px] pb-3 border-b border-[var(--color-border)]">
		<Eyebrow>AGENTS · {runs.length} · {activeCount} ACTIVE</Eyebrow>
		<Heading size="md">Runs</Heading>
	</header>
	<div class="flex gap-1.5 px-4 py-2.5 border-b border-[var(--color-border)]">
		{#each filters as f (f)}
			<button type="button" onclick={() => (filter = f)} class="cursor-pointer" aria-pressed={filter === f}>
				<Chip tone={filter === f ? 'ink' : 'outline'}>{f}</Chip>
			</button>
		{/each}
	</div>
	<div class="flex-1 overflow-y-auto">
		{#each visible as run (run.id)}
			<AgentRow {run} active={run.id === activeId} href="/agents/{run.kind}/{run.id}" />
		{/each}
	</div>
</aside>
