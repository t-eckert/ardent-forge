<script lang="ts">
	import { cn } from '$lib/utils/cn';

	interface Props {
		/** Initial or 1–2 char label */
		label: string;
		/** Background colour key from the palette — defaults to ember */
		tone?: 'ember' | 'signal' | 'graphite' | 'ink' | 'moss' | 'warn';
		size?: 'sm' | 'md' | 'lg';
		class?: string;
	}

	let { label, tone = 'ember', size = 'md', class: klass }: Props = $props();

	const toneClass = $derived(
		{
			ember: 'bg-[var(--color-ember)]',
			signal: 'bg-[var(--color-signal)]',
			graphite: 'bg-[var(--color-graphite)]',
			ink: 'bg-[var(--color-ink)]',
			moss: 'bg-[var(--color-moss)]',
			warn: 'bg-[var(--color-warn)]'
		}[tone]
	);

	const sizeClass = $derived(
		{
			sm: 'w-5 h-5 text-[10px]',
			md: 'w-6 h-6 text-[11px]',
			lg: 'w-8 h-8 text-[13px]'
		}[size]
	);
</script>

<span
	class={cn(
		'inline-flex items-center justify-center rounded-[4px] text-[var(--color-paper)] font-mono',
		toneClass,
		sizeClass,
		klass
	)}
>
	{label}
</span>
