<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';

	interface Props {
		/** visual size — xl is hero page titles, lg is section heroes, md is card titles */
		size?: 'md' | 'lg' | 'xl';
		/** semantic heading level (defaults to h1) */
		as?: 'h1' | 'h2' | 'h3' | 'div';
		class?: string;
		children: Snippet;
	}

	let { size = 'lg', as = 'h1', class: klass, children }: Props = $props();

	const sizeClass = $derived(
		{
			md: 'text-2xl leading-tight',
			lg: 'text-5xl leading-[1.05]',
			xl: 'text-6xl leading-[1.02]'
		}[size]
	);
</script>

<svelte:element
	this={as}
	class={cn('font-display font-medium text-[var(--color-ink)]', sizeClass, klass)}
>
	{@render children()}
</svelte:element>
