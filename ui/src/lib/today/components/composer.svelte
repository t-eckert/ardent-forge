<script lang="ts">
	import { Eyebrow, Meta } from '$lib/typography';
	import { Chip, KeycapHint } from '$lib/components';

	interface Props {
		placeholder?: string;
		scopeChips?: string[];
		modelLabel?: string;
	}

	let {
		placeholder = 'Start a thread from here — e.g. "plan the week around the long run"',
		scopeChips = ['@today', '@health', '/tools']
	}: Props = $props();
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
		<span class="flex-1 text-sm text-[var(--color-graphite)]">{placeholder}</span>
		<KeycapHint keys={['⌘', '↵']} />
	</div>
</div>
