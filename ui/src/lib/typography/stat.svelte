<script lang="ts">
	import { cn } from '$lib/utils/cn';

	/**
	 * The canonical way to render a number in Ardent Forge.
	 *
	 * Wrap every numeric value in this component — it enforces the "numbers always mono"
	 * rule (see memory/feedback_numbers_mono.md). Never render raw numbers in a Playfair
	 * or Inter context; wrap them here.
	 *
	 * @example
	 *   <Stat value="46" unit="km" />
	 *   <Stat value="1:48:22" size="lg" />
	 *   <Stat value="82" unit="/100" size="xl" />
	 */
	interface Props {
		value: string | number;
		unit?: string;
		size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl';
		tone?: 'default' | 'muted' | 'ember' | 'moss' | 'warn';
		class?: string;
	}

	let { value, unit, size = 'md', tone = 'default', class: klass }: Props = $props();

	const sizeClass = $derived(
		{
			xs: 'text-[11px]',
			sm: 'text-[13px]',
			md: 'text-[16px]',
			lg: 'text-[22px]',
			xl: 'text-[34px]',
			'2xl': 'text-[40px]'
		}[size]
	);

	const unitSizeClass = $derived(
		{
			xs: 'text-[10px]',
			sm: 'text-[11px]',
			md: 'text-[12px]',
			lg: 'text-[14px]',
			xl: 'text-[16px]',
			'2xl': 'text-[20px]'
		}[size]
	);

	const toneClass = $derived(
		{
			default: 'text-[var(--color-ink)]',
			muted: 'text-[var(--color-graphite)]',
			ember: 'text-[var(--color-ember-deep)]',
			moss: 'text-[var(--color-moss)]',
			warn: 'text-[var(--color-warn)]'
		}[tone]
	);
</script>

<span class={cn('font-mono inline-flex items-baseline gap-1', sizeClass, toneClass, klass)}>
	<span>{value}</span>
	{#if unit}
		<span class={cn('text-[var(--color-graphite)]', unitSizeClass)}>{unit}</span>
	{/if}
</span>
