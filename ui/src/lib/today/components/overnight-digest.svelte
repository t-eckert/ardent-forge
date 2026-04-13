<script lang="ts">
	import type { AgentRun } from '$lib/schemas/agent';
	import { Heading, Meta } from '$lib/typography';
	import { Chip, StatusDot } from '$lib/components';
	import { formatTime } from '$lib/utils/date';

	interface Props {
		runs: AgentRun[];
	}

	let { runs }: Props = $props();

	const toneFor = (status: AgentRun['status']) => {
		if (status === 'needs-review') return 'ember' as const;
		if (status === 'failed') return 'warn' as const;
		return 'moss' as const;
	};

	const chipFor = (status: AgentRun['status']) => {
		if (status === 'needs-review') return { label: 'needs review', tone: 'ember' as const };
		if (status === 'failed') return { label: 'failed', tone: 'ember' as const };
		if (status === 'cron') return { label: 'cron', tone: 'moss' as const };
		if (status === 'watching') return { label: 'watching', tone: 'moss' as const };
		return { label: 'done', tone: 'moss' as const };
	};
</script>

<section class="flex flex-col gap-2.5">
	<header class="flex items-end justify-between pb-1.5 border-b border-[var(--color-border)]">
		<div class="flex items-baseline gap-2.5">
			<Heading size="md">Overnight</Heading>
			<Meta size="sm">{runs.length} AGENTS</Meta>
		</div>
		<a href="/agents" class="font-mono text-[11px] text-[var(--color-ember-deep)]">agents →</a>
	</header>
	<div class="flex flex-col gap-2.5">
		{#each runs as run (run.id)}
			{@const chip = chipFor(run.status)}
			<a
				href={run.href ?? '/agents'}
				class="flex flex-col gap-1.5 p-3 bg-[var(--color-paper)] border border-[var(--color-border)] rounded-md hover:border-[var(--color-stone)] transition-colors"
			>
				<div class="flex items-center justify-between">
					<div class="flex items-center gap-2">
						<StatusDot tone={toneFor(run.status)} />
						<Meta size="sm">{run.kind} · {formatTime(run.startedIso)} · {run.durationLabel}</Meta>
					</div>
					<Chip tone={chip.tone}>{chip.label}</Chip>
				</div>
				<span class="text-[13px] text-[var(--color-ink)]">{run.summary}</span>
			</a>
		{/each}
	</div>
</section>
