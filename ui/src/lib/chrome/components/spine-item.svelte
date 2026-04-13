<script lang="ts">
	import type { Component } from 'svelte';
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';

	interface Props {
		href: string;
		label: string;
		icon: Component;
		active?: boolean;
		/** Right-aligned meta (day of week, count, live pip, etc.) */
		meta?: Snippet;
	}

	let { href, label, icon: Icon, active = false, meta }: Props = $props();
</script>

<a
	{href}
	class={cn(
		'flex items-center justify-between gap-3 px-2.5 py-2 text-[13px] rounded-md transition-colors',
		active
			? 'bg-[var(--color-paper)] border border-[var(--color-border)] text-[var(--color-ink)] font-medium'
			: 'text-[var(--color-slate)] hover:bg-[var(--color-paper)]/60'
	)}
>
	<span class="flex items-center gap-2.5 min-w-0">
		<Icon size={16} weight="regular" color={active ? 'var(--color-ember)' : 'var(--color-graphite)'} />
		<span class="truncate">{label}</span>
	</span>
	{#if meta}
		{@render meta()}
	{/if}
</a>
