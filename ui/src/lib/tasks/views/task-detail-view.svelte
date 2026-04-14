<script lang="ts">
	import type { Task } from '$lib/schemas/task';
	import TaskList from '../components/task-list.svelte';
	import TaskHeader from '../components/task-header.svelte';
	import TaskStageStrip from '../components/task-stage-strip.svelte';
	import { Body, Eyebrow } from '$lib/typography';

	interface Props {
		tasks: Task[];
		active: Task;
	}

	let { tasks, active }: Props = $props();

	const handlerEntries = $derived(Object.entries(active.handler_data ?? {}));
	const resultEntries = $derived(active.result ? Object.entries(active.result) : []);
</script>

<div class="flex min-h-[calc(100vh-3rem)]">
	<TaskList {tasks} activeId={active.id} />
	<section class="flex-1 min-w-0 overflow-y-auto">
		<TaskHeader task={active} />
		<TaskStageStrip task={active} />

		<div class="px-10 py-6 flex flex-col gap-6">
			<div class="flex flex-col gap-2">
				<Eyebrow>DESCRIPTION</Eyebrow>
				<Body>{active.description}</Body>
			</div>

			{#if handlerEntries.length}
				<div class="flex flex-col gap-2">
					<Eyebrow>HANDLER DATA</Eyebrow>
					<dl class="grid grid-cols-[200px_1fr] gap-y-1 gap-x-4 font-mono text-[12px]">
						{#each handlerEntries as [k, v] (k)}
							<dt class="text-[var(--color-slate)]">{k}</dt>
							<dd class="text-[var(--color-ink)] break-all">{typeof v === 'string' ? v : JSON.stringify(v)}</dd>
						{/each}
					</dl>
				</div>
			{/if}

			{#if resultEntries.length}
				<div class="flex flex-col gap-2">
					<Eyebrow>RESULT</Eyebrow>
					<dl class="grid grid-cols-[200px_1fr] gap-y-1 gap-x-4 font-mono text-[12px]">
						{#each resultEntries as [k, v] (k)}
							<dt class="text-[var(--color-slate)]">{k}</dt>
							<dd class="text-[var(--color-ink)] break-all">{typeof v === 'string' ? v : JSON.stringify(v)}</dd>
						{/each}
					</dl>
				</div>
			{/if}

			{#if active.retries > 0}
				<div class="flex flex-col gap-2">
					<Eyebrow>RETRIES</Eyebrow>
					<Body muted>This task was retried <span class="font-mono">{active.retries}</span> time(s).</Body>
				</div>
			{/if}
		</div>
	</section>
</div>
