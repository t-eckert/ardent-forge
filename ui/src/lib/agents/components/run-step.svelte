<script lang="ts">
	import type { RunStep } from '$lib/schemas/agent';
	import { Meta } from '$lib/typography';
	import { formatTime } from '$lib/utils/date';

	interface Props {
		step: RunStep;
		isLast?: boolean;
	}

	let { step, isLast = false }: Props = $props();

	const marker = $derived(
		{
			done: { glyph: '✓', bg: '#E8F0E6', fg: '#3C6A4A' },
			waiting: { glyph: '?', bg: '#FCE6DD', fg: 'var(--color-ember-deep)' },
			failed: { glyph: '✗', bg: '#FDECE4', fg: 'var(--color-ember-deep)' }
		}[step.state]
	);
</script>

<div
	class="flex items-start gap-3.5 py-2.5"
	class:border-b={!isLast}
	style={!isLast ? 'border-color: var(--color-border)' : ''}
>
	<span class="w-[70px] font-mono text-[11px] text-[var(--color-graphite)] flex-shrink-0">
		{formatTime(step.atIso)}
	</span>
	<span
		class="inline-flex items-center justify-center w-[18px] h-[18px] rounded-full font-mono text-[10px] flex-shrink-0"
		style="background: {marker.bg}; color: {marker.fg};"
	>
		{marker.glyph}
	</span>
	<div class="flex flex-col gap-0.5 flex-1 min-w-0">
		<span class="text-[13px] text-[var(--color-ink)]">{step.summary}</span>
		<Meta size="xs" tone={step.state === 'waiting' ? 'ember' : 'muted'}>{step.meta}</Meta>
	</div>
</div>
