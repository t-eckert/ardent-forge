<script lang="ts">
	import { Display, Heading, Eyebrow, Body, Meta } from '$lib/typography';
	import { Card, Chip } from '$lib/components';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

<div class="flex flex-col gap-8 px-14 py-9 max-w-[1200px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>LIBRARY · REPOS</Eyebrow>
		<Display size="lg">Repos</Display>
		<Heading size="sm" italic>Git repositories scanned from the workspace.</Heading>
	</div>

	{#if data.repos.length === 0}
		<Body muted>No repositories found. Add repos to ~/Repos and restart Forge.</Body>
	{:else}
		<div class="grid grid-cols-2 gap-4">
			{#each data.repos as repo (repo.name)}
				<Card surface="paper" class="p-5">
					<div class="flex flex-col gap-2">
						<div class="flex items-center justify-between gap-2">
							<Heading size="sm">{repo.name}</Heading>
						</div>
						<div class="flex flex-col gap-0.5">
							<Meta size="xs">branch: {repo.default_branch}</Meta>
							<Meta size="xs">{repo.path}</Meta>
						</div>
					</div>
				</Card>
			{/each}
		</div>
	{/if}
</div>
