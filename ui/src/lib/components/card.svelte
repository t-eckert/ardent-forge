<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cva, type VariantProps } from 'cva';
	import { cn } from '$lib/utils/cn';

	const card = cva({
		base: 'rounded-[8px] overflow-hidden',
		variants: {
			surface: {
				paper: 'bg-[var(--color-paper)] border border-[var(--color-border)]',
				bench: 'bg-[var(--color-bench)] border border-[var(--color-border)]',
				ember: 'text-[var(--color-paper)] bg-gradient-to-br from-[#E34E18] to-[#C73D0F]',
				/** dashed border, used for "new" placeholder slots */
				empty: 'bg-[var(--color-paper)] border border-dashed border-[var(--color-stone)]'
			}
		},
		defaultVariants: { surface: 'paper' }
	});

	type Surface = VariantProps<typeof card>['surface'];

	interface Props {
		surface?: Surface;
		class?: string;
		children: Snippet;
	}

	let { surface = 'paper', class: klass, children }: Props = $props();
</script>

<div class={cn(card({ surface }), klass)}>
	{@render children()}
</div>
