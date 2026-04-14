<script lang="ts">
	import type { SavedMemory } from '$lib/schemas/thread';
	import { Meta } from '$lib/typography';

	interface Props {
		memory: SavedMemory;
	}

	let { memory }: Props = $props();
</script>

<!--
  Small inline pill — Forge's acknowledgement that it wrote a memory. Placed
  after the prose, before any widgets. Deliberately quiet: memory writes
  should not break conversational rhythm.
-->
<span
	class="inline-flex items-baseline gap-1.5 px-2 py-[3px] rounded-[3px] bg-[var(--color-bench)] border border-[var(--color-border)] w-fit"
>
	<span class="font-mono text-[10px] text-[var(--color-moss)] tracking-wider">◈ saved</span>
	<span class="font-mono text-[11px] text-[var(--color-slate)]">{memory.type}</span>
	<span class="text-[11px] text-[var(--color-ink)]">— {memory.name}</span>
</span>
