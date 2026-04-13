<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';

	/**
	 * JetBrains Mono label text — 10–11px, used for metadata rows, tool badges,
	 * source tags, timestamps, and any inline meta that isn't a number.
	 */
	interface Props {
		size?: 'xs' | 'sm';
		tone?: 'default' | 'muted' | 'ember' | 'moss' | 'warn';
		as?: 'span' | 'div';
		class?: string;
		children: Snippet;
	}

	let { size = 'xs', tone = 'muted', as = 'span', class: klass, children }: Props = $props();

	const sizeClass = $derived({ xs: 'text-[10px]', sm: 'text-[11px]' }[size]);

	const toneClass = $derived(
		{
			default: 'text-[var(--color-ink)]',
			muted: 'text-[var(--color-graphite)]',
			ember: 'text-[var(--color-ember-deep)]',
			moss: 'text-[var(--color-moss)]',
			warn: 'text-[var(--color-warn)]'
		}[tone]
	);
</script>

<svelte:element this={as} class={cn('font-mono', sizeClass, toneClass, klass)}>
	{@render children()}
</svelte:element>
