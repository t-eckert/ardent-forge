<script lang="ts">
	import { Meta } from '$lib/typography';
	import { Chip, KeycapHint } from '$lib/components';

	interface Props {
		scopeChips?: string[];
		modelLabel?: string;
		placeholder?: string;
	}

	let {
		scopeChips = ['@thread', '@today', '/tools'],
		modelLabel = 'claude-opus-4-6 · code+tools',
		placeholder = 'Continue the thread…'
	}: Props = $props();
</script>

<div
	class="flex flex-col gap-2.5 p-4 bg-[var(--color-bench)] border-t border-[var(--color-border)]"
>
	<div class="flex items-center justify-between">
		<div class="flex gap-1.5">
			{#each scopeChips as chip (chip)}
				<Chip tone="outline">{chip}</Chip>
			{/each}
		</div>
		<Meta size="sm">{modelLabel}</Meta>
	</div>
	<div
		class="flex items-center gap-2.5 px-3 py-2.5 bg-[var(--color-paper)] border border-[var(--color-stone)] rounded-md"
	>
		<span class="flex-1 text-sm text-[var(--color-graphite)]">{placeholder}</span>
		<KeycapHint keys={['⌘', '↵']} />
	</div>
</div>
