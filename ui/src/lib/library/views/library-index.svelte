<script lang="ts">
	import { Display, Body, Heading, Eyebrow } from '$lib/typography';
	import { Card } from '$lib/components';

	interface Counts {
		log: number;
		wiki: number;
		fields: number;
		people: number;
		collections: number;
	}

	interface Props {
		counts?: Counts | null;
		agentCount?: number;
		connectorCount?: number;
		memoryCount?: number;
	}

	let {
		counts = null,
		agentCount = 0,
		connectorCount = 0,
		memoryCount = 0
	}: Props = $props();

	function fmt(n: number): string {
		return n.toLocaleString();
	}

	interface Facet {
		label: string;
		href: string;
		count: string;
		group: 'Content' | 'System';
		description?: string;
	}

	const facets = $derived<Facet[]>([
		{ label: 'Fields', href: '/library/fields', count: fmt(counts?.fields ?? 0), group: 'Content' },
		{ label: 'Daily log', href: '/library/log', count: fmt(counts?.log ?? 0), group: 'Content' },
		{ label: 'Wiki', href: '/library/wiki', count: fmt(counts?.wiki ?? 0), group: 'Content' },
		{ label: 'People', href: '/library/people', count: fmt(counts?.people ?? 0), group: 'Content' },
		{ label: 'Collections', href: '/library/collections', count: fmt(counts?.collections ?? 0), group: 'Content' },
		{
			label: 'Agents',
			href: '/library/agents',
			count: String(agentCount),
			group: 'System',
			description: 'Specialist processors Forge dispatches work to'
		},
		{
			label: 'Connectors',
			href: '/library/connectors',
			count: String(connectorCount),
			group: 'System',
			description: 'External capabilities — weather, github, linear, notebook'
		},
		{
			label: 'Memory',
			href: '/library/memory',
			count: String(memoryCount),
			group: 'System',
			description: "What Forge has learned about you — user-editable"
		}
	]);

	const content = $derived(facets.filter((f) => f.group !== 'System'));
	const system = $derived(facets.filter((f) => f.group === 'System'));
</script>

<div class="flex flex-col gap-8 px-14 py-9 max-w-[1200px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>LIBRARY</Eyebrow>
		<Display size="lg">Library</Display>
		<Heading size="sm" italic>Everything structured — content you own, and the machinery Forge runs on.</Heading>
	</div>

	<div class="flex flex-col gap-3">
		<Eyebrow>CONTENT</Eyebrow>
		<div class="grid grid-cols-2 gap-4">
			{#each content as f (f.label)}
				<a href={f.href}>
					<Card surface="paper" class="transition-colors hover:border-[var(--color-stone)]">
						<div class="flex items-center justify-between p-5">
							<Heading size="sm">{f.label}</Heading>
							<span class="font-mono text-[var(--color-graphite)]">{f.count}</span>
						</div>
					</Card>
				</a>
			{/each}
		</div>
	</div>

	<div class="flex flex-col gap-3 pt-4 border-t border-[var(--color-border)]">
		<Eyebrow>SYSTEM</Eyebrow>
		<div class="grid grid-cols-3 gap-4">
			{#each system as f (f.label)}
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
</div>
