<script lang="ts">
	import type { ResolvedTask } from '$lib/schemas/thread';
	import { Body, Meta } from '$lib/typography';
	import { WidgetHost } from '$lib/widgets';

	interface Props {
		task: ResolvedTask;
		/** Prose Forge wrote on resolution — typically a one-liner narration. */
		narration?: string;
	}

	let { task, narration }: Props = $props();
</script>

<div class="flex flex-col gap-2.5 max-w-[820px]">
	<Meta size="sm">RESOLVED · {task.agent}</Meta>
	{#if narration}
		<Body>{narration}</Body>
	{:else}
		<Body>{task.summary}</Body>
	{/if}
	<Meta size="xs">
		<a href="/tasks/{task.id}" class="hover:text-[var(--color-ember-deep)]">task {task.id} →</a>
	</Meta>
	{#if task.artifact}
		<WidgetHost payload={task.artifact} />
	{/if}
</div>
