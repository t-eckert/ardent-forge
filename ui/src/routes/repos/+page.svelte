<script lang="ts">
	import { untrack } from 'svelte';
	import { Display, Heading, Eyebrow, Body, Meta } from '$lib/typography';
	import { Card, Chip, Button, Spinner } from '$lib/components';
	import type { PageData } from './$types';
	import type { Repo } from '$lib/api/typed';
	import { api } from '$lib/api/typed';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();

	// untrack: intentionally snapshot data.repos at load time; clone mutations update independently
	let repos = $state<Repo[]>(untrack(() => [...data.repos]));
	let cloneUrl = $state('');
	let cloning = $state(false);
	let cloneError = $state<string | null>(null);
	let cloneSuccess = $state<string | null>(null);

	async function handleClone() {
		const url = cloneUrl.trim();
		if (!url) return;
		cloning = true;
		cloneError = null;
		cloneSuccess = null;
		try {
			const repo = await api.repos.clone(url);
			if (!repos.some((r) => r.name === repo.name)) {
				repos = [...repos, repo].sort((a, b) => a.name.localeCompare(b.name));
			}
			cloneSuccess = repo.name;
			cloneUrl = '';
		} catch (e) {
			cloneError = e instanceof Error ? e.message : 'Clone failed';
		} finally {
			cloning = false;
		}
	}

	type Group = { label: string; repos: Repo[] };

	function groupRepos(repoList: Repo[]): Group[] {
		const groups = new Map<string, Repo[]>();
		for (const repo of repoList) {
			const parts = repo.name.split('/');
			const label =
				parts.length >= 3
					? `${parts[0]} / ${parts[1]}`
					: parts.length === 2
						? parts[0]
						: 'workspace';
			if (!groups.has(label)) groups.set(label, []);
			groups.get(label)!.push(repo);
		}
		return [...groups.entries()]
			.map(([label, repos]) => ({ label, repos }))
			.sort((a, b) => {
				if (a.label === 'workspace') return -1;
				if (b.label === 'workspace') return 1;
				return a.label.localeCompare(b.label);
			});
	}

	function repoName(name: string): string {
		const parts = name.split('/');
		return parts[parts.length - 1];
	}

	let groups = $derived(groupRepos(repos));
</script>

<div class="flex flex-col gap-8 px-14 py-9 max-w-[1200px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>REPOS</Eyebrow>
		<Display size="lg">Repos</Display>
		<Heading size="sm" italic>Git repositories scanned from ~/Repos.</Heading>
	</div>

	<!-- Clone form -->
	<Card surface="paper" class="p-5">
		<div class="flex flex-col gap-3">
			<Eyebrow>CLONE</Eyebrow>
			<div class="flex gap-2">
				<input
					type="text"
					bind:value={cloneUrl}
					placeholder="owner/repo  ·  https://github.com/owner/repo  ·  git@github.com:owner/repo"
					class="flex-1 h-8 px-3 text-[13px] font-mono bg-[var(--color-bench)] border border-[var(--color-border)] rounded-md placeholder:text-[var(--color-stone)] focus:outline-none focus:ring-1 focus:ring-[var(--color-ember)] focus:border-[var(--color-ember)] disabled:opacity-50"
					disabled={cloning}
					onkeydown={(e) => e.key === 'Enter' && handleClone()}
				/>
				<Button variant="primary" size="md" onclick={handleClone} disabled={cloning || !cloneUrl.trim()}>
					{#if cloning}
						<Spinner size="sm" />
						Cloning…
					{:else}
						Clone
					{/if}
				</Button>
			</div>
			{#if cloneError}
				<Meta tone="ember">{cloneError}</Meta>
			{/if}
			{#if cloneSuccess}
				<Meta tone="moss">Cloned → {cloneSuccess}</Meta>
			{/if}
		</div>
	</Card>

	<!-- Repo list -->
	{#if repos.length === 0}
		<Card surface="empty">
			<div class="flex flex-col gap-2 p-8 items-center">
				<Eyebrow>EMPTY</Eyebrow>
				<Body muted>No repositories found. Clone one above or add repos to ~/Repos and restart Forge.</Body>
			</div>
		</Card>
	{:else}
		<div class="flex flex-col gap-8">
			{#each groups as group (group.label)}
				<div class="flex flex-col gap-3">
					<div class="px-0.5">
						<Eyebrow>{group.label}</Eyebrow>
					</div>
					<div class="grid grid-cols-2 gap-3 xl:grid-cols-3">
						{#each group.repos as repo (repo.name)}
							<Card surface="paper" class="p-5">
								<div class="flex flex-col gap-2">
									<div class="flex items-start justify-between gap-2">
										<Heading size="sm">{repoName(repo.name)}</Heading>
										<Chip tone="outline">{repo.default_branch}</Chip>
									</div>
									<Meta>{repo.path}</Meta>
								</div>
							</Card>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
