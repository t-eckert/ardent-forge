<script lang="ts">
	import { goto } from '$app/navigation';
	import { Eyebrow, Meta } from '$lib/typography';
	import { api } from '$lib/api/typed';
	import type { Repo } from '$lib/api/typed';

	interface Props {
		repos?: Repo[];
		agentTypes?: string[];
	}

	let { repos = [], agentTypes = ['code', 'plan', 'echo'] }: Props = $props();

	let prompt = $state('');
	let repo = $state<string>('');
	let agentType = $state<string>('code');
	let sending = $state(false);
	let error = $state<string | null>(null);

	async function submit() {
		const description = prompt.trim();
		if (!description || sending) return;
		sending = true;
		error = null;
		try {
			const title = description.length > 60 ? description.slice(0, 57) + '…' : description;
			const task = await api.tasks.create({
				type: agentType,
				title,
				description,
				repo: repo || null
			});
			await goto(`/tasks/${task.id}`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to dispatch task';
			sending = false;
		}
	}

	function onkey(e: KeyboardEvent) {
		if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			submit();
		}
	}
</script>

<div
	class="flex flex-col gap-2.5 p-4 bg-[var(--color-bench)] border border-[var(--color-border)] rounded-[8px]"
>
	<Eyebrow>DISPATCH A TASK</Eyebrow>
	<textarea
		bind:value={prompt}
		onkeydown={onkey}
		placeholder="Describe the work — e.g. 'add a /health/ready endpoint and a test'"
		rows="3"
		class="w-full resize-none bg-transparent text-sm text-[var(--color-ink)] outline-none placeholder:text-[var(--color-graphite)]"
	></textarea>
	<div class="flex items-center gap-2">
		<select
			bind:value={repo}
			class="bg-[var(--color-paper)] border border-[var(--color-border)] rounded px-2 py-1 text-[12px]"
		>
			<option value="">(no repo)</option>
			{#each repos as r (r.name)}
				<option value={r.name}>{r.name}</option>
			{/each}
		</select>
		<select
			bind:value={agentType}
			class="bg-[var(--color-paper)] border border-[var(--color-border)] rounded px-2 py-1 text-[12px]"
		>
			{#each agentTypes as a (a)}
				<option value={a}>{a}</option>
			{/each}
		</select>
		<div class="flex-1"></div>
		<button
			onclick={submit}
			disabled={sending || !prompt.trim()}
			class="bg-[var(--color-ember)] text-[var(--color-paper)] rounded px-3 py-1 text-[12px] font-medium disabled:opacity-50"
		>
			{sending ? 'Dispatching…' : 'Dispatch'}
		</button>
	</div>
	{#if error}
		<Meta size="xs">{error}</Meta>
	{/if}
</div>
