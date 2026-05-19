<script lang="ts">
	import { Display, Body, Heading, Eyebrow } from '$lib/typography';
	import { Card } from '$lib/components';

	interface Props {
		agentCount?: number;
		connectorCount?: number;
		memoryCount?: number;
		repoCount?: number;
		scheduleCount?: number;
	}

	let {
		agentCount = 0,
		connectorCount = 0,
		memoryCount = 0,
		repoCount = 0,
		scheduleCount = 0
	}: Props = $props();

	interface Facet {
		label: string;
		href: string;
		count: string;
		description?: string;
	}

	const facets = $derived<Facet[]>([
		{
			label: 'Repos',
			href: '/library/repos',
			count: String(repoCount),
			description: 'Git repositories scanned from the workspace'
		},
		{
			label: 'Schedules',
			href: '/library/schedules',
			count: String(scheduleCount),
			description: 'Cron schedules that fire tasks automatically'
		},
		{
			label: 'Agents',
			href: '/library/agents',
			count: String(agentCount),
			description: 'Specialist processors Forge dispatches work to'
		},
		{
			label: 'Connectors',
			href: '/library/connectors',
			count: String(connectorCount),
			description: 'External capabilities — github, 1password, web search'
		},
		{
			label: 'Memory',
			href: '/library/memory',
			count: String(memoryCount),
			description: "What Forge has learned about you — user-editable"
		},
		{
			label: 'Log',
			href: '/library/log',
			count: '—',
			description: 'Coordinator activity and task history'
		}
	]);
</script>

<div class="flex flex-col gap-8 px-14 py-9 max-w-[1200px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>LIBRARY</Eyebrow>
		<Display size="lg">Library</Display>
		<Heading size="sm" italic>Repos, agents, connectors, and everything Forge runs on.</Heading>
	</div>

	<div class="grid grid-cols-3 gap-4">
		{#each facets as f (f.label)}
			<a href={f.href}>
				<Card surface="paper" class="transition-colors hover:border-[var(--color-stone)] h-full">
					<div class="flex flex-col gap-2 p-5 h-full">
						<div class="flex items-center justify-between">
							<Heading size="sm">{f.label}</Heading>
							<span class="font-mono text-[var(--color-graphite)]">{f.count}</span>
						</div>
						{#if f.description}
							<Body size="sm" muted>{f.description}</Body>
						{/if}
					</div>
				</Card>
			</a>
		{/each}
	</div>
</div>
