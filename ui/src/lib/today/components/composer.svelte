<script lang="ts">
	import { goto } from '$app/navigation';
	import { Eyebrow, Meta } from '$lib/typography';
	import { Chip, KeycapHint } from '$lib/components';
	import { api } from '$lib/api/typed';

	interface Props {
		placeholder?: string;
		scopeChips?: string[];
		modelLabel?: string;
	}

	let {
		placeholder = 'Start a thread — e.g. "plan the week around the long run"',
		scopeChips = ['@today', '@health', '/tools']
	}: Props = $props();

	let value = $state('');
	let sending = $state(false);

	async function submit() {
		const content = value.trim();
		if (!content || sending) return;
		sending = true;
		try {
			const title = content.length > 60 ? content.slice(0, 57) + '…' : content;
			const thread = await api.threads.create(title);
			// Navigate with the message as a query param so the thread view
			// can auto-send it and stream the response.
			const q = new URLSearchParams({ send: content });
			await goto(`/threads/${thread.id}?${q}`);
		} finally {
			sending = false;
		}
	}

	function onkey(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			submit();
		}
	}
</script>

<div
	class="flex flex-col gap-2.5 p-4 bg-[var(--color-bench)] border border-[var(--color-border)] rounded-[8px]"
>
	<div class="flex items-center justify-between">
		<Eyebrow>ASK THE FORGE</Eyebrow>
		<div class="flex gap-1.5">
			{#each scopeChips as chip (chip)}
				<Chip tone="outline">{chip}</Chip>
			{/each}
		</div>
	</div>
	<div
		class="flex items-center gap-2.5 px-3 py-2.5 bg-[var(--color-paper)] border border-[var(--color-stone)] rounded-md"
	>
		<input
			type="text"
			bind:value
			{placeholder}
			disabled={sending}
			onkeydown={onkey}
			class="flex-1 bg-transparent text-sm text-[var(--color-ink)] placeholder:text-[var(--color-graphite)] outline-none"
			aria-label="Message"
		/>
		<KeycapHint keys={['↵']} />
	</div>
</div>
