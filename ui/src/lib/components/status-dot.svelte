<script lang="ts">
	import { cva, type VariantProps } from 'cva';
	import { cn } from '$lib/utils/cn';

	const dot = cva({
		base: 'inline-block rounded-full',
		variants: {
			tone: {
				ember: 'bg-[var(--color-ember)]',
				moss: 'bg-[var(--color-moss)]',
				warn: 'bg-[var(--color-warn)]',
				signal: 'bg-[var(--color-signal)]',
				graphite: 'bg-[var(--color-graphite)]',
				stone: 'bg-[var(--color-stone)]'
			},
			size: {
				xs: 'w-1.5 h-1.5',
				sm: 'w-2 h-2',
				md: 'w-2.5 h-2.5'
			}
		},
		defaultVariants: { tone: 'moss', size: 'xs' }
	});

	type Tone = VariantProps<typeof dot>['tone'];
	type Size = VariantProps<typeof dot>['size'];

	interface Props {
		tone?: Tone;
		size?: Size;
		class?: string;
	}

	let { tone = 'moss', size = 'xs', class: klass }: Props = $props();
</script>

<span class={cn(dot({ tone, size }), klass)} aria-hidden="true"></span>
