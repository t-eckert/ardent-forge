<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import { cva, type VariantProps } from 'cva';
	import { cn } from '$lib/utils/cn';

	const button = cva({
		base: 'inline-flex items-center justify-center gap-2 rounded-md font-sans font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ember)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--color-paper)]',
		variants: {
			variant: {
				primary:
					'bg-[var(--color-ink)] text-[var(--color-paper)] hover:bg-[var(--color-ember-deep)]',
				secondary:
					'bg-[var(--color-paper)] text-[var(--color-ink)] border border-[var(--color-stone)] hover:bg-[var(--color-bench)]',
				ghost: 'text-[var(--color-ink)] hover:bg-[var(--color-bench)]',
				danger: 'bg-[var(--color-ember-deep)] text-[var(--color-paper)] hover:opacity-90'
			},
			size: {
				sm: 'h-7 px-3 text-[12px]',
				md: 'h-8 px-3.5 text-[13px]',
				lg: 'h-10 px-4 text-sm'
			}
		},
		defaultVariants: {
			variant: 'secondary',
			size: 'md'
		}
	});

	type Variant = VariantProps<typeof button>['variant'];
	type Size = VariantProps<typeof button>['size'];

	interface Props extends Omit<HTMLButtonAttributes, 'class'> {
		variant?: Variant;
		size?: Size;
		class?: string;
		children: Snippet;
	}

	let { variant = 'secondary', size = 'md', class: klass, children, ...rest }: Props = $props();
</script>

<button class={cn(button({ variant, size }), klass)} {...rest}>
	{@render children()}
</button>
