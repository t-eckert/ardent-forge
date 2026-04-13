<script lang="ts">
	import { cn } from '$lib/utils/cn';

	/**
	 * Renders a keyboard shortcut hint.
	 * @example <KeycapHint keys={['⌘', 'K']} />
	 */
	interface Props {
		keys: string[];
		class?: string;
	}

	let { keys, class: klass }: Props = $props();
</script>

<span class={cn('inline-flex items-center gap-1', klass)}>
	{#each keys as key (key)}
		<kbd
			class="font-mono text-[10px] leading-none text-[var(--color-ink)] bg-[var(--color-paper)] border border-[var(--color-stone)] rounded-[3px] px-1.5 py-1"
		>
			{key}
		</kbd>
	{/each}
</span>
