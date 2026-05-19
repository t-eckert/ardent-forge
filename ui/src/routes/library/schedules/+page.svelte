<script lang="ts">
	import { Display, Heading, Eyebrow, Body, Meta } from '$lib/typography';
	import { Card, Chip } from '$lib/components';
	import { formatRelative } from '$lib/utils/date';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

<div class="flex flex-col gap-8 px-14 py-9 max-w-[1200px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>LIBRARY · SCHEDULES</Eyebrow>
		<Display size="lg">Schedules</Display>
		<Heading size="sm" italic>Cron schedules that fire tasks automatically.</Heading>
	</div>

	{#if data.schedules.length === 0}
		<Body muted>No schedules configured yet.</Body>
	{:else}
		<div class="flex flex-col gap-3">
			{#each data.schedules as sched (sched.id)}
				<Card surface="paper" class="p-5">
					<div class="flex items-start justify-between gap-4">
						<div class="flex flex-col gap-1 flex-1 min-w-0">
							<div class="flex items-center gap-2">
								<Heading size="sm">{sched.name}</Heading>
								{#if !sched.enabled}
									<Chip tone="neutral">disabled</Chip>
								{/if}
							</div>
							<div class="flex gap-4">
								<Meta size="xs">cron: {sched.cron_expr}</Meta>
								<Meta size="xs">type: {sched.task_type}</Meta>
							</div>
						</div>
						<div class="flex flex-col gap-0.5 text-right flex-shrink-0">
							{#if sched.next_run}
								<Meta size="xs">next: {formatRelative(sched.next_run)}</Meta>
							{/if}
							{#if sched.last_run}
								<Meta size="xs">last: {formatRelative(sched.last_run)}</Meta>
							{/if}
						</div>
					</div>
				</Card>
			{/each}
		</div>
	{/if}
</div>
