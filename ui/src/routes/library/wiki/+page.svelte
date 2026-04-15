<script lang="ts">
	import { Display, Eyebrow, Heading, Meta } from '$lib/typography';
	import { Card } from '$lib/components';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();

	// Separate files from directories.
	const pages = $derived(data.entries.filter((e: string) => e.endsWith('.md')).map((e: string) => e.replace(/\.md$/, '')));
	const folders = $derived(data.entries.filter((e: string) => !e.endsWith('.md') && !e.startsWith('.')));

	// Group pages by first letter.
	const grouped = $derived.by(() => {
		const map = new Map<string, string[]>();
		for (const name of pages) {
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
		<Eyebrow>LIBRARY · WIKI</Eyebrow>
		<div class="flex items-end justify-between">
			<Display size="lg">Wiki</Display>
			<Meta size="sm">{pages.length} pages · {folders.length} categories</Meta>
		</div>
		<Heading size="sm" italic>Reference pages — concepts, tools, people, places.</Heading>
	</div>

	{#if folders.length > 0}
		<div class="flex flex-col gap-2">
			<Eyebrow>CATEGORIES</Eyebrow>
			<div class="grid grid-cols-3 gap-3">
				{#each folders as folder (folder)}
					<a href="/library/wiki/{encodeURIComponent(folder)}">
						<Card surface="paper" class="transition-colors hover:border-[var(--color-stone)]">
							<div class="flex items-center justify-between px-5 py-3">
								<span class="text-[14px] text-[var(--color-ink)]">{folder}</span>
								<Meta size="xs">→</Meta>
							</div>
						</Card>
					</a>
				{/each}
			</div>
		</div>
	{/if}

	{#each grouped as [letter, names] (letter)}
		<div class="flex flex-col gap-1.5">
			<Eyebrow>{letter}</Eyebrow>
			<div class="flex flex-wrap gap-x-6 gap-y-1">
				{#each names as name (name)}
					<a
						href="/library/wiki/{encodeURIComponent(name)}"
						class="text-[14px] text-[var(--color-ink)] hover:text-[var(--color-ember-deep)]"
					>
						{name}
					</a>
				{/each}
			</div>
		</div>
	{/each}
</div>
