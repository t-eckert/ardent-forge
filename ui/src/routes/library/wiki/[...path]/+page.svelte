<script lang="ts">
	import { Display, Eyebrow, Body, Meta } from '$lib/typography';
	import { Card } from '$lib/components';
	import Markdown from '$lib/components/markdown.svelte';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();

	const pages = $derived(
		'entries' in data && data.entries
			? data.entries.filter((e: string) => e.endsWith('.md')).map((e: string) => e.replace(/\.md$/, ''))
			: []
	);
	const folders = $derived(
		'entries' in data && data.entries
			? data.entries.filter((e: string) => !e.endsWith('.md') && !e.startsWith('.'))
			: []
	);
</script>

<div class="flex flex-col gap-6 px-14 py-9 max-w-[860px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<a href="/library/wiki" class="font-mono text-[11px] text-[var(--color-ember-deep)]">
			← Wiki
		</a>
		<Eyebrow>WIKI · {data.title?.toUpperCase()}</Eyebrow>
		<Display size="lg">{data.title}</Display>
	</div>

	{#if data.kind === 'page' && 'body' in data && data.body}
		<Markdown source={data.body} />
	{:else if data.kind === 'directory'}
		{#if folders.length > 0}
			<div class="flex flex-col gap-2">
				<Eyebrow>SUBCATEGORIES</Eyebrow>
				<div class="grid grid-cols-3 gap-3">
					{#each folders as folder (folder)}
						<a href="/library/wiki/{data.path}/{encodeURIComponent(folder)}">
							<Card surface="paper" class="transition-colors hover:border-[var(--color-stone)]">
								<div class="px-5 py-3 text-[14px] text-[var(--color-ink)]">{folder}</div>
							</Card>
						</a>
					{/each}
				</div>
			</div>
		{/if}
		{#if pages.length > 0}
			<div class="flex flex-col gap-1.5">
				<Eyebrow>PAGES</Eyebrow>
				<div class="flex flex-wrap gap-x-6 gap-y-1">
					{#each pages as name (name)}
						<a
							href="/library/wiki/{data.path}/{encodeURIComponent(name)}"
							class="text-[14px] text-[var(--color-ink)] hover:text-[var(--color-ember-deep)]"
						>
							{name}
						</a>
					{/each}
				</div>
			</div>
		{/if}
	{:else}
		<Body muted>Page not found: {data.path}</Body>
	{/if}
</div>
