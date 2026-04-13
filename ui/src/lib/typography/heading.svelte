<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';

	interface Props {
		size?: 'sm' | 'md' | 'lg';
		as?: 'h2' | 'h3' | 'h4' | 'div';
		italic?: boolean;
		class?: string;
		children: Snippet;
	}

	let { size = 'md', as = 'h2', italic = false, class: klass, children }: Props = $props();

	const sizeClass = $derived(
		{
			sm: 'text-lg leading-snug',
			md: 'text-[22px] leading-snug',
			lg: 'text-[28px] leading-[1.15]'
		}[size]
	);
</script>

<svelte:element
	this={as}
	class={cn(
		'font-display font-medium text-[var(--color-ink)]',
		sizeClass,
		italic && 'italic font-normal',
		klass
	)}
>
	{@render children()}
</svelte:element>
