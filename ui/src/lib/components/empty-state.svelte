<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';

	interface Props {
		title?: string;
		message?: string;
		class?: string;
		children?: Snippet;
	}

	let { title, message, class: klass, children }: Props = $props();
</script>

<div
	class={cn(
		'flex flex-col items-center justify-center gap-2 py-10 text-center',
		'text-[var(--color-graphite)] font-mono text-[11px] tracking-wider',
		klass
	)}
>
	{#if title}<div class="text-[var(--color-slate)] text-sm font-sans">{title}</div>{/if}
	{#if message}<div>{message}</div>{/if}
	{#if children}{@render children()}{/if}
</div>
