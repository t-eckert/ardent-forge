<script lang="ts">
	import { Display, Eyebrow, Heading, Meta } from '$lib/typography';
	import { Card } from '$lib/components';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();

	function dayLabel(iso: string): string {
		try {
			return new Date(iso + 'T12:00:00').toLocaleDateString('en-US', {
				weekday: 'long',
				month: 'short',
				day: 'numeric',
				year: 'numeric'
			});
		} catch {
			return iso;
		}
	}

	// Group entries by month.
	const grouped = $derived.by(() => {
		const map = new Map<string, string[]>();
		for (const date of data.entries) {
			const month = date.slice(0, 7); // "2026-04"
			const list = map.get(month) ?? [];
			list.push(date);
			map.set(month, list);
		}
		return [...map.entries()];
	});

	function monthLabel(ym: string): string {
		try {
			return new Date(ym + '-15').toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
		} catch {
			return ym;
		}
	}
</script>

<div class="flex flex-col gap-8 px-14 py-9 max-w-[1200px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>LIBRARY · DAILY LOG</Eyebrow>
		<div class="flex items-end justify-between">
			<Display size="lg">Daily log</Display>
			<Meta size="sm">{data.entries.length} entries</Meta>
		</div>
		<Heading size="sm" italic>One page per day — observations, tasks, and reflections.</Heading>
	</div>

	{#each grouped as [month, dates] (month)}
		<div class="flex flex-col gap-2">
			<Eyebrow>{monthLabel(month).toUpperCase()}</Eyebrow>
			<div class="flex flex-col gap-1.5">
				{#each dates as date (date)}
					<a href="/library/log/{date}">
						<Card surface="paper" class="transition-colors hover:border-[var(--color-stone)]">
							<div class="flex items-center justify-between px-5 py-3">
								<span class="text-[14px] text-[var(--color-ink)]">{dayLabel(date)}</span>
								<Meta size="xs">{date}</Meta>
							</div>
						</Card>
					</a>
				{/each}
			</div>
		</div>
	{/each}
</div>
