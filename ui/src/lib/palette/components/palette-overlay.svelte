<script lang="ts">
	import { Command } from 'bits-ui';
	import type { PaletteResult } from '../types';
	import ResultRow from './result-row.svelte';
	import { palette } from '../state/palette.state.svelte';
	import { Eyebrow, Meta } from '$lib/typography';
	import { KeycapHint } from '$lib/components';
	import { goto } from '$app/navigation';

	interface Props {
		results: PaletteResult[];
	}

	let { results }: Props = $props();

	// Group results by class for display
	const groups = $derived.by(() => {
		const byClass = new Map<PaletteResult['class'], PaletteResult[]>();
		for (const r of results) {
			const arr = byClass.get(r.class) ?? [];
			arr.push(r);
			byClass.set(r.class, arr);
		}
		return byClass;
	});

	const classLabels: Record<PaletteResult['class'], string> = {
		task: 'TASKS',
		note: 'NOTES',
		thread: 'THREADS',
		action: 'ACTIONS'
	};

	const order: PaletteResult['class'][] = ['task', 'thread', 'note', 'action'];

	function handleSelect(result: PaletteResult) {
		palette.hide();
		if (result.href) goto(result.href);
		// TODO: dispatch action for 'action' class results
	}
</script>

{#if palette.open}
	<!-- Scrim -->
	<div
		class="fixed inset-0 z-50 bg-[rgba(26,23,20,0.38)] flex justify-center items-start pt-[140px] px-4"
		onclick={() => palette.hide()}
		role="presentation"
	>
		<!-- Palette card; stop propagation so clicks inside don't close -->
		<div
			class="w-full max-w-[640px] bg-[var(--color-paper)] border border-[var(--color-stone)] rounded-[10px] overflow-hidden shadow-[0_24px_80px_rgba(26,23,20,0.22)]"
			onclick={(e) => e.stopPropagation()}
			role="presentation"
		>
			<Command.Root label="Command palette" loop>
				<div
					class="flex items-center gap-3 px-[18px] py-3.5 border-b border-[var(--color-border)] bg-[var(--color-paper)]"
				>
					<Meta size="sm">⌘K</Meta>
					<Command.Input
						placeholder="Search everything…"
						class="flex-1 bg-transparent text-[16px] text-[var(--color-ink)] focus:outline-none placeholder:text-[var(--color-graphite)]"
					/>
					<KeycapHint keys={['esc']} />
				</div>

				<Command.List class="max-h-[420px] overflow-y-auto py-1.5">
					<Command.Empty class="py-8 text-center">
						<Meta size="xs">No results</Meta>
					</Command.Empty>

					{#each order as cls (cls)}
						{@const items = groups.get(cls) ?? []}
						{#if items.length > 0}
							<Command.Group>
								<Command.GroupHeading class="px-[18px] pt-2.5 pb-1.5 block">
									<Eyebrow>{classLabels[cls]}</Eyebrow>
								</Command.GroupHeading>
								<Command.GroupItems>
									{#each items as result (result.id)}
										<ResultRow {result} onselect={handleSelect} />
									{/each}
								</Command.GroupItems>
							</Command.Group>
						{/if}
					{/each}
				</Command.List>

				<div
					class="flex items-center justify-between px-4 py-2.5 border-t border-[var(--color-border)] bg-[var(--color-bench)]"
				>
					<div class="flex items-center gap-3 font-mono text-[10px] text-[var(--color-graphite)]">
						<span class="inline-flex items-center gap-1"
							><KeycapHint keys={['↑']} /><KeycapHint keys={['↓']} /> navigate</span
						>
						<span class="inline-flex items-center gap-1"><KeycapHint keys={['↵']} /> open</span>
						<span class="inline-flex items-center gap-1"
							><KeycapHint keys={['⌘', '↵']} /> open in new thread</span
						>
					</div>
					<Meta size="xs">fuzzy</Meta>
				</div>
			</Command.Root>
		</div>
	</div>
{/if}
