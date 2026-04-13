<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cva, type VariantProps } from 'cva';
	import { cn } from '$lib/utils/cn';

	const chip = cva({
		base: 'inline-flex items-center gap-1 rounded-[2px] font-mono text-[10px] leading-none px-1.5 py-[3px]',
		variants: {
			tone: {
				neutral: 'bg-[var(--color-bench)] text-[var(--color-slate)]',
				ember: 'bg-[#FCE6DD] text-[var(--color-ember-deep)]',
				moss: 'bg-[#E8F0E6] text-[#3C6A4A]',
				ink: 'bg-[var(--color-ink)] text-[var(--color-paper)]',
				outline:
					'bg-[var(--color-paper)] text-[var(--color-slate)] border border-[var(--color-stone)]'
			}
		},
		defaultVariants: { tone: 'neutral' }
	});

	type Tone = VariantProps<typeof chip>['tone'];

	interface Props {
		tone?: Tone;
		class?: string;
		children: Snippet;
	}

	let { tone = 'neutral', class: klass, children }: Props = $props();
</script>

<span class={cn(chip({ tone }), klass)}>
	{@render children()}
</span>
