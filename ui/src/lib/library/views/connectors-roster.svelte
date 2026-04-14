<script lang="ts">
	import { Display, Eyebrow, Heading, Meta, Body } from '$lib/typography';
	import { Card, Chip, Avatar, StatusDot } from '$lib/components';

	interface ConnectorTool {
		name: string;
		description: string;
		long_running: boolean;
	}

	interface ConnectorRow {
		name: string;
		tools: ConnectorTool[];
		health?: 'live' | 'synced' | 'stale' | 'failing' | 'unknown';
	}

	interface Props {
		connectors: ConnectorRow[];
	}

	let { connectors }: Props = $props();

	function badgeFor(name: string): { label: string; tone: 'ember' | 'signal' | 'graphite' | 'ink' } {
		const map: Record<string, any> = {
			weather: { label: '☀', tone: 'ember' },
			strava: { label: 'S', tone: 'ember' },
			github: { label: '{}', tone: 'ink' },
			linear: { label: 'L', tone: 'signal' },
			notebook: { label: '¶', tone: 'graphite' },
			osm: { label: '◎', tone: 'signal' },
			plaid: { label: '$', tone: 'ink' },
			uptime: { label: '↑', tone: 'graphite' }
		};
		return map[name] ?? { label: name[0]?.toUpperCase() ?? '?', tone: 'graphite' };
	}

	// StatusDot accepts 'graphite'; Meta expects 'muted'. Compute both.
	function dotTone(h?: string): 'moss' | 'warn' | 'graphite' {
		if (h === 'live' || h === 'synced') return 'moss';
		if (h === 'stale' || h === 'failing') return 'warn';
		return 'graphite';
	}
	function textTone(h?: string): 'moss' | 'warn' | 'muted' {
		if (h === 'live' || h === 'synced') return 'moss';
		if (h === 'stale' || h === 'failing') return 'warn';
		return 'muted';
	}

	function healthLabel(h?: string): string {
		if (h === 'live') return '● live';
		if (h === 'synced') return '● synced';
		if (h === 'stale') return '◑ stale';
		if (h === 'failing') return '✗ failing';
		return '○ unknown';
	}
</script>

<div class="flex flex-col gap-8 px-14 py-9 max-w-[1200px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>LIBRARY · CONNECTORS</Eyebrow>
		<Display size="lg">Connectors</Display>
		<Heading size="sm" italic>
			External capabilities Forge has access to. Each connector owns its auth + health; its tools are available to every agent and every chat turn.
		</Heading>
	</div>

	<div class="flex flex-col gap-4">
		{#each connectors as c (c.name)}
			{@const badge = badgeFor(c.name)}
			<Card surface="paper">
				<div class="flex flex-col gap-4 p-6">
					<div class="flex items-center gap-3">
						<Avatar label={badge.label} tone={badge.tone} size="lg" />
						<div class="flex flex-col gap-0.5 flex-1">
							<Heading size="md">{c.name}</Heading>
							<Meta size="xs">{c.tools.length} tool{c.tools.length === 1 ? '' : 's'}</Meta>
						</div>
						<span class="inline-flex items-center gap-1.5">
							<StatusDot tone={dotTone(c.health)} />
							<Meta tone={textTone(c.health)}>{healthLabel(c.health)}</Meta>
						</span>
					</div>

					<div class="flex flex-col gap-2 pt-2 border-t border-[var(--color-border)]">
						<Eyebrow>TOOLS</Eyebrow>
						{#each c.tools as t (t.name)}
							<div class="flex items-start gap-2 py-1">
								<span class="font-mono text-[12px] text-[var(--color-ink)] min-w-[160px]">{t.name}</span>
								<Body size="sm" muted>{t.description}</Body>
								{#if t.long_running}
									<Chip tone="ember">long-running</Chip>
								{/if}
							</div>
						{/each}
					</div>
				</div>
			</Card>
		{/each}

		{#if connectors.length === 0}
			<Card surface="empty">
				<div class="flex flex-col gap-2 p-8 items-center">
					<Eyebrow>EMPTY</Eyebrow>
					<Body muted>No connectors registered.</Body>
				</div>
			</Card>
		{/if}
	</div>
</div>
