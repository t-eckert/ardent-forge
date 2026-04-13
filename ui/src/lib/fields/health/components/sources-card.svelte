<script lang="ts">
	import { Card, Avatar, StatusDot } from '$lib/components';
	import { Eyebrow, Meta } from '$lib/typography';

	interface SourceRow {
		key: string;
		label: string;
		description: string;
		tone: 'ember' | 'signal' | 'graphite' | 'ink';
		status: 'live' | 'synced' | 'optional';
	}

	interface Props {
		sources?: SourceRow[];
	}

	let {
		sources = [
			{ key: 'S', label: 'Strava', description: 'runs · HR · pace', tone: 'ember', status: 'live' },
			{ key: 'N', label: 'Notebook', description: 'strength · mobility', tone: 'signal', status: 'synced' },
			{
				key: 'G',
				label: 'Garmin',
				description: 'sleep · HRV',
				tone: 'graphite',
				status: 'optional'
			}
		]
	}: Props = $props();

	const toneFor = (s: SourceRow['status']) =>
		s === 'live' ? ('moss' as const) : s === 'synced' ? ('moss' as const) : ('muted' as const);
	const labelFor = (s: SourceRow['status']) =>
		s === 'live' ? '● live' : s === 'synced' ? '● synced' : '○ optional';
</script>

<Card surface="paper">
	<div class="flex flex-col gap-3.5 p-[18px]">
		<Eyebrow>SOURCES</Eyebrow>
		{#each sources as s (s.key)}
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-2.5">
					<Avatar label={s.key} tone={s.tone} />
					<div class="flex flex-col gap-0.5">
						<span class="text-[13px] font-medium text-[var(--color-ink)]">{s.label}</span>
						<Meta size="xs">{s.description}</Meta>
					</div>
				</div>
				<Meta tone={toneFor(s.status)}>{labelFor(s.status)}</Meta>
			</div>
		{/each}
	</div>
</Card>
