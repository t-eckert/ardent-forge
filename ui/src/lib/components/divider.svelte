<script lang="ts">
	import { cn } from '$lib/utils/cn';

	interface Props {
		orientation?: 'horizontal' | 'vertical';
		class?: string;
	}

	let { orientation = 'horizontal', class: klass }: Props = $props();
</script>

<div
	role="separator"
	aria-orientation={orientation}
	class={cn(
		'bg-[var(--color-border)]',
		orientation === 'horizontal' ? 'h-px w-full' : 'w-px h-full',
		klass
	)}
></div>
