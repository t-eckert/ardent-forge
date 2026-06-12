<script lang="ts">
	import type { AgentRun } from '$lib/schemas/agent';
	import { Display, Eyebrow, Heading, Meta, Body } from '$lib/typography';
	import { Card, Chip, Avatar } from '$lib/components';

	interface AgentRosterRow {
		name: string;
		task_type: string;
		stages: string[];
		connectors: string[];
	}

	interface Props {
		agents: AgentRosterRow[];
		recentRuns?: AgentRun[];
	}

	let { agents, recentRuns = [] }: Props = $props();

	function badgeFor(name: string): { label: string; tone: 'ink' | 'signal' | 'graphite' | 'ember' | 'warn' } {
		const map: Record<string, any> = {
			code: { label: '{}', tone: 'ink' },
			'code-agent': { label: '{}', tone: 'ink' },
			plan: { label: '§', tone: 'signal' },
			tickets: { label: '→', tone: 'ember' },
			echo: { label: '·', tone: 'graphite' }
		};
		return map[name] ?? { label: name[0]?.toUpperCase() ?? '?', tone: 'ink' };
	}

	function runsFor(task_type: string): AgentRun[] {
		return recentRuns.filter((r) => r.kind === task_type).slice(0, 3);
	}
</script>

<div class="flex flex-col gap-8 px-14 py-9 max-w-[1200px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>LIBRARY · AGENTS</Eyebrow>
		<Display size="lg">Agents</Display>
		<Heading size="sm" italic>
			Specialists Forge dispatches work to. Each declares which stages it uses and which connectors it needs.
		</Heading>
	</div>

	<div class="flex flex-col gap-4">
		{#each agents as agent (agent.task_type)}
			{@const badge = badgeFor(agent.name)}
			{@const runs = runsFor(agent.task_type)}
			<Card surface="paper">
				<div class="flex flex-col gap-4 p-6">
					<div class="flex items-center gap-3">
						<Avatar label={badge.label} tone={badge.tone} size="lg" />
						<div class="flex flex-col gap-0.5 flex-1">
							<Heading size="md">{agent.name}</Heading>
							<Meta size="xs">task_type · {agent.task_type}</Meta>
						</div>
					</div>

					<div class="flex gap-8">
						<div class="flex flex-col gap-1">
							<Eyebrow>STAGES</Eyebrow>
							<div class="flex gap-1 flex-wrap">
								{#each agent.stages as stage (stage)}
									<Chip tone="outline">{stage}</Chip>
								{/each}
							</div>
						</div>
						<div class="flex flex-col gap-1">
							<Eyebrow>CONNECTORS</Eyebrow>
							<div class="flex gap-1 flex-wrap">
								{#if agent.connectors.length === 0}
									<Meta size="xs">· none declared ·</Meta>
								{:else}
									{#each agent.connectors as c (c)}
										<Chip tone="neutral">{c}</Chip>
									{/each}
								{/if}
							</div>
						</div>
					</div>

					{#if runs.length > 0}
						<div class="flex flex-col gap-2 pt-2 border-t border-[var(--color-border)]">
							<Eyebrow>RECENT RUNS</Eyebrow>
							{#each runs as run (run.id)}
								<a
									href="/tasks/{run.id}"
									class="flex items-center justify-between text-[13px] hover:bg-[var(--color-bench)] rounded px-2 py-1"
								>
									<span class="text-[var(--color-ink)]">{run.summary}</span>
									<Meta size="xs">{run.durationLabel} · {run.status}</Meta>
								</a>
							{/each}
						</div>
					{/if}
				</div>
			</Card>
		{/each}

		{#if agents.length === 0}
			<Card surface="empty">
				<div class="flex flex-col gap-2 p-8 items-center">
					<Eyebrow>EMPTY</Eyebrow>
					<Body muted>No agents registered.</Body>
				</div>
			</Card>
		{/if}
	</div>
</div>
