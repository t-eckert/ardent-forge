<script lang="ts">
	import { Heading, Eyebrow, Body, Meta } from '$lib/typography';
	import { Card, StatusDot, Chip } from '$lib/components';
	import { OpenThreads } from '$lib/today';
	import type { Thread } from '$lib/schemas/thread';
	import type { AgentRun } from '$lib/schemas/agent';
	import type { Task } from '$lib/schemas/task';
	import type { Repo } from '$lib/api/typed';
	import { formatRelative } from '$lib/utils/date';

	interface Props {
		threads?: Thread[];
		activeTasks?: Task[];
		queuedTasks?: Task[];
		recentTasks?: AgentRun[];
		repos?: Repo[];
	}

	let {
		threads = [],
		activeTasks = [],
		queuedTasks = [],
		recentTasks = [],
		repos = []
	}: Props = $props();

	function statusTone(status: Task['status']): 'ember' | 'moss' | 'stone' {
		if (status === 'failed') return 'ember';
		if (['verifying', 'delivering'].includes(status)) return 'moss';
		return 'moss';
	}

	function statusLabel(status: Task['status']): string {
		const map: Record<string, string> = {
			triaging: 'triaging',
			executing: 'executing',
			verifying: 'verifying',
			delivering: 'delivering'
		};
		return map[status] ?? status;
	}

	const today = new Date().toLocaleDateString('en-US', {
		weekday: 'long',
		month: 'long',
		day: 'numeric'
	});
</script>

<div class="flex flex-col gap-7 px-14 pt-9 pb-6 max-w-[1440px] mx-auto">
	<div class="flex flex-col gap-1">
		<Eyebrow>DASHBOARD</Eyebrow>
		<Heading size="lg">{today}</Heading>
	</div>

	<div class="flex gap-9">
		<!-- Left column: tasks -->
		<div class="flex flex-col flex-1 gap-8 min-w-0">

			<!-- Active tasks -->
			<section class="flex flex-col gap-2.5">
				<header class="flex items-end justify-between pb-1.5 border-b border-[var(--color-border)]">
					<div class="flex items-baseline gap-2.5">
						<Heading size="md">Active</Heading>
						{#if activeTasks.length > 0}
							<Meta size="sm">{activeTasks.length} RUNNING</Meta>
						{/if}
					</div>
					<a href="/tasks" class="font-mono text-[11px] text-[var(--color-ember-deep)]">tasks →</a>
				</header>
				{#if activeTasks.length === 0}
					<Body size="sm" muted>No active tasks.</Body>
				{:else}
					<div class="flex flex-col gap-2">
						{#each activeTasks as task (task.id)}
							<a
								href="/tasks/{task.id}"
								class="flex items-center gap-3 p-3 bg-[var(--color-paper)] border border-[var(--color-border)] rounded-md hover:border-[var(--color-stone)] transition-colors"
							>
								<StatusDot tone={statusTone(task.status)} />
								<div class="flex flex-col gap-0.5 flex-1 min-w-0">
									<span class="text-[13px] font-medium text-[var(--color-ink)] truncate">{task.title}</span>
									{#if task.repo}
										<Meta size="xs">{task.repo}</Meta>
									{/if}
								</div>
								<Chip tone="moss">{statusLabel(task.status)}</Chip>
							</a>
						{/each}
					</div>
				{/if}
			</section>

			<!-- Queue -->
			{#if queuedTasks.length > 0}
				<section class="flex flex-col gap-2.5">
					<header class="flex items-end justify-between pb-1.5 border-b border-[var(--color-border)]">
						<div class="flex items-baseline gap-2.5">
							<Heading size="md">Queued</Heading>
							<Meta size="sm">{queuedTasks.length} WAITING</Meta>
						</div>
					</header>
					<div class="flex flex-col gap-1.5">
						{#each queuedTasks as task (task.id)}
							<a
								href="/tasks/{task.id}"
								class="flex items-center gap-3 py-2"
							>
								<StatusDot tone="stone" />
								<span class="text-[13px] text-[var(--color-ink)] truncate flex-1">{task.title}</span>
								{#if task.repo}
									<Meta size="xs">{task.repo}</Meta>
								{/if}
							</a>
						{/each}
					</div>
				</section>
			{/if}

			<!-- Recent -->
			{#if recentTasks.length > 0}
				<section class="flex flex-col gap-2.5">
					<header class="pb-1.5 border-b border-[var(--color-border)]">
						<Heading size="md">Recent</Heading>
					</header>
					<div class="flex flex-col gap-1.5">
						{#each recentTasks as run (run.id)}
							<a
								href={run.href ?? '/tasks'}
								class="flex items-center gap-3 py-2 border-b border-[var(--color-border)] last:border-0"
							>
								<StatusDot tone={run.status === 'failed' ? 'ember' : 'stone'} />
								<span class="text-[13px] text-[var(--color-ink)] truncate flex-1">{run.summary}</span>
								<Meta size="xs">{run.durationLabel}</Meta>
							</a>
						{/each}
					</div>
				</section>
			{/if}
		</div>

		<!-- Right column: repos + threads -->
		<div class="flex flex-col w-[360px] gap-7 flex-shrink-0">

			<!-- Repos -->
			<section class="flex flex-col gap-2.5">
				<header class="flex items-end justify-between pb-1.5 border-b border-[var(--color-border)]">
					<div class="flex items-baseline gap-2.5">
						<Heading size="md">Repos</Heading>
						<Meta size="sm">{repos.length} SCANNED</Meta>
					</div>
					<a href="/library/repos" class="font-mono text-[11px] text-[var(--color-ember-deep)]">all →</a>
				</header>
				{#if repos.length === 0}
					<Body size="sm" muted>No repos found in workspace.</Body>
				{:else}
					<div class="flex flex-col gap-1.5">
						{#each repos as repo (repo.name)}
							<Card surface="paper" class="p-3">
								<div class="flex items-center justify-between gap-2">
									<div class="flex flex-col gap-0.5 min-w-0">
										<span class="text-[13px] font-medium text-[var(--color-ink)] truncate">{repo.name}</span>
										<Meta size="xs">{repo.default_branch}</Meta>
									</div>
									{#if repo.dev_port}
										<Chip tone="moss">:{repo.dev_port}</Chip>
									{/if}
								</div>
							</Card>
						{/each}
					</div>
				{/if}
			</section>

			<!-- Open threads -->
			<OpenThreads {threads} />
		</div>
	</div>
</div>
