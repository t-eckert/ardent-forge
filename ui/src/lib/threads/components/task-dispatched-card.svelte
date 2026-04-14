<script lang="ts">
	import type { DispatchedTask } from '$lib/schemas/thread';
	import { Card, Chip, StatusDot } from '$lib/components';
	import { Eyebrow, Meta } from '$lib/typography';

	interface Props {
		task: DispatchedTask;
	}

	let { task }: Props = $props();

	const statusChip = $derived(
		task.status === 'needs-review'
			? { label: 'needs review', tone: 'ember' as const }
			: task.status === 'failed'
				? { label: 'failed', tone: 'ember' as const }
				: task.status === 'done'
					? { label: 'done', tone: 'moss' as const }
					: { label: task.status, tone: 'moss' as const }
	);
</script>

<Card surface="paper" class="max-w-[760px]">
	<div class="flex flex-col gap-3 p-4">
		<div class="flex items-center justify-between gap-3">
			<div class="flex items-center gap-2">
				<StatusDot tone={task.status === 'needs-review' || task.status === 'failed' ? 'ember' : 'moss'} />
				<Meta size="sm">DISPATCHED · {task.agent} · {task.id}</Meta>
			</div>
			<Chip tone={statusChip.tone}>{statusChip.label}</Chip>
		</div>

		<a href="/tasks/{task.id}" class="text-[15px] font-medium text-[var(--color-ink)] hover:underline">
			{task.title}
		</a>

		<div class="flex flex-wrap gap-1.5 pt-1 border-t border-[var(--color-border)]">
			<Eyebrow>STAGES</Eyebrow>
			{#each task.stages as stage (stage)}
				{@const active = stage === task.currentStage}
				{@const past =
					!active &&
					task.stages.indexOf(stage) <
						(task.currentStage ? task.stages.indexOf(task.currentStage) : task.stages.length)}
				<Chip tone={active ? 'ember' : past ? 'moss' : 'outline'}>
					{active ? '▸' : past ? '✓' : '○'} {stage}
				</Chip>
			{/each}
		</div>
	</div>
</Card>
