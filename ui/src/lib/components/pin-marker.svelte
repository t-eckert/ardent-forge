<script lang="ts">
	import { cn } from '$lib/utils/cn';

	/**
	 * Map pin — used by places-map widget and anywhere a pinned location is shown.
	 * The teardrop shape is a rotated square with one rounded corner.
	 */
	interface Props {
		label: string | number;
		active?: boolean;
		size?: 'sm' | 'md';
		class?: string;
	}

	let { label, active = false, size = 'md', class: klass }: Props = $props();

	const sizeClass = $derived(
		{ sm: 'w-5 h-5 text-[10px]', md: 'w-7 h-7 text-[12px]' }[size]
	);
</script>

<span
	class={cn(
		'inline-flex items-center justify-center rounded-full rounded-bl-none text-[var(--color-paper)] font-mono -rotate-45',
		active ? 'bg-[var(--color-ember)]' : 'bg-[var(--color-ink)]',
		sizeClass,
		klass
	)}
>
	<span class="rotate-45">{label}</span>
</span>
