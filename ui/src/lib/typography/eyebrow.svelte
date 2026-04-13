<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';

	/**
	 * Letter-spaced uppercase mono label — used above titles, at the top of cards,
	 * and for section identifiers like "FIELD · HEALTH · WORKOUTS" or "RESULTS".
	 */
	interface Props {
		tone?: 'default' | 'ember' | 'warn';
		class?: string;
		children: Snippet;
	}

	let { tone = 'default', class: klass, children }: Props = $props();

	const toneClass = $derived(
		{
			default: 'text-[var(--color-graphite)]',
			ember: 'text-[var(--color-ember)]',
			warn: 'text-[var(--color-warn)]'
		}[tone]
	);
</script>

<span class={cn('font-mono text-[10px] tracking-[0.12em] uppercase', toneClass, klass)}>
	{@render children()}
</span>
