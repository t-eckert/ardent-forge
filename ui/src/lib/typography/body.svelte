<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';

	interface Props {
		size?: 'sm' | 'md' | 'lg';
		muted?: boolean;
		as?: 'p' | 'span' | 'div';
		class?: string;
		children: Snippet;
	}

	let { size = 'md', muted = false, as = 'p', class: klass, children }: Props = $props();

	const sizeClass = $derived(
		{
			sm: 'text-xs leading-relaxed',
			md: 'text-sm leading-relaxed',
			lg: 'text-base leading-relaxed'
		}[size]
	);
</script>

<svelte:element
	this={as}
	class={cn(
		'font-sans',
		muted ? 'text-[var(--color-slate)]' : 'text-[var(--color-ink)]',
		sizeClass,
		klass
	)}
>
	{@render children()}
</svelte:element>
