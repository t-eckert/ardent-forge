<script lang="ts">
	import type { RunStep } from '$lib/schemas/agent';
	import RunStepRow from './run-step.svelte';
	import { Heading, Meta } from '$lib/typography';

	interface Props {
		steps: RunStep[];
	}

	let { steps }: Props = $props();

	const stateLine = $derived.by(() => {
		const done = steps.filter((s) => s.state === 'done').length;
		const blocked = steps.some((s) => s.state === 'waiting');
		const failed = steps.some((s) => s.state === 'failed');
		if (failed) return `${steps.length} STEPS · 1 FAILED`;
		if (blocked) return `${steps.length} STEPS · AWAITING REVIEW`;
		return `${steps.length} STEPS · ALL GREEN`;
	});
</script>

<section class="flex flex-col gap-3.5">
	<header class="flex items-end justify-between pb-1.5 border-b border-[var(--color-border)]">
		<div class="flex items-baseline gap-2.5">
			<Heading size="md">Timeline</Heading>
			<Meta size="sm">{stateLine}</Meta>
		</div>
		<a href="#log" class="font-mono text-[11px] text-[var(--color-ember-deep)]">view full log →</a>
	</header>
	<div class="flex flex-col">
		{#each steps as step, i (step.id)}
			<RunStepRow {step} isLast={i === steps.length - 1} />
		{/each}
	</div>
</section>
