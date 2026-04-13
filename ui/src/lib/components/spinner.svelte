<script lang="ts">
	import { cn } from '$lib/utils/cn';

	interface Props {
		size?: 'sm' | 'md' | 'lg';
		class?: string;
	}

	let { size = 'md', class: klass }: Props = $props();

	const sizeClass = $derived({ sm: 'w-3 h-3', md: 'w-4 h-4', lg: 'w-5 h-5' }[size]);
</script>

<span
	class={cn(
		'inline-block animate-spin rounded-full border-2 border-[var(--color-stone)] border-t-[var(--color-ember)]',
		sizeClass,
		klass
	)}
	role="status"
	aria-label="Loading"
></span>
