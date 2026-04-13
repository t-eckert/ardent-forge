<script lang="ts">
	import { Command } from 'bits-ui';
	import type { PaletteResult } from '../types';
	import { Sun, ChatCircle, Heartbeat, Code, ListChecks, ArrowRight } from '$lib/icons';
	import { Meta } from '$lib/typography';

	interface Props {
		result: PaletteResult;
		onselect: (r: PaletteResult) => void;
	}

	let { result, onselect }: Props = $props();

	// Icon + tone per result class
	const classConfig = {
		workout: { icon: Heartbeat, bg: 'var(--color-ember)' },
		note: { icon: Code, bg: 'var(--color-signal)' },
		task: { icon: ListChecks, bg: 'var(--color-bench)', fg: 'var(--color-slate)' },
		thread: { icon: ChatCircle, bg: 'var(--color-graphite)' },
		action: { icon: ArrowRight, bg: 'var(--color-ink)' }
	} as const;

	const cfg = $derived(classConfig[result.class]);
	const fg = $derived('fg' in cfg ? cfg.fg : 'var(--color-paper)');
	const Icon = $derived(cfg.icon);
</script>

<Command.Item
	value={result.label + ' ' + (result.keywords ?? []).join(' ')}
	onSelect={() => onselect(result)}
	class="flex items-center gap-3 px-[18px] py-2.5 cursor-pointer data-[selected=true]:bg-[var(--color-bench)] data-[selected=true]:border-l-2 data-[selected=true]:border-[var(--color-ember)] aria-selected:bg-[var(--color-bench)]"
>
	<span
		class="flex items-center justify-center w-[22px] h-[22px] rounded-[4px] flex-shrink-0"
		style="background: {cfg.bg}; color: {fg};"
	>
		<Icon size={12} weight="regular" />
	</span>
	<div class="flex flex-col flex-1 min-w-0 gap-0.5">
		<div class="flex items-baseline gap-2 min-w-0">
			<span class="text-[14px] text-[var(--color-ink)] truncate">{result.label}</span>
			{#if result.hint}
				<Meta size="xs">· {result.hint}</Meta>
			{/if}
		</div>
		<Meta size="sm">{result.breadcrumb}</Meta>
	</div>
</Command.Item>
