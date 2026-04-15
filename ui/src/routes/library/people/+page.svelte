<script lang="ts">
	import { Display, Eyebrow, Heading, Meta } from '$lib/typography';
	import { Card } from '$lib/components';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();

	// Group by first letter.
	const grouped = $derived.by(() => {
		const map = new Map<string, string[]>();
		for (const name of data.people) {
			const letter = name[0]?.toUpperCase() ?? '#';
			const list = map.get(letter) ?? [];
			list.push(name);
			map.set(letter, list);
		}
		return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
	});
</script>

<div class="flex flex-col gap-8 px-14 py-9 max-w-[1200px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>LIBRARY · PEOPLE</Eyebrow>
		<div class="flex items-end justify-between">
			<Display size="lg">People</Display>
			<Meta size="sm">{data.people.length} entries</Meta>
		</div>
		<Heading size="sm" italic>Colleagues, collaborators, friends, mentors — everyone in the graph.</Heading>
	</div>

	{#each grouped as [letter, names] (letter)}
		<div class="flex flex-col gap-1.5">
			<Eyebrow>{letter}</Eyebrow>
			<div class="grid grid-cols-3 gap-2">
				{#each names as name (name)}
					<a href="/library/people/{encodeURIComponent(name)}">
						<Card surface="paper" class="transition-colors hover:border-[var(--color-stone)]">
							<div class="px-4 py-2.5 text-[14px] text-[var(--color-ink)]">{name}</div>
						</Card>
					</a>
				{/each}
			</div>
		</div>
	{/each}
</div>
