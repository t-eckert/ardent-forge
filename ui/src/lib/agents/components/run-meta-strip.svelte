<script lang="ts">
	import type { AgentRunDetail } from '$lib/schemas/agent';
	import { Eyebrow, Stat } from '$lib/typography';

	interface Props {
		metas: AgentRunDetail['metas'];
	}

	let { metas }: Props = $props();

	const toneFor = (t?: string) =>
		t === 'ember' ? 'ember' : t === 'moss' ? 'moss' : t === 'warn' ? 'warn' : 'default';
</script>

<div
	class="flex gap-6 px-[18px] py-3.5 bg-[var(--color-bench)] border border-[var(--color-border)] rounded-lg flex-wrap"
>
	{#each metas as m (m.label)}
		<div class="flex flex-col gap-0.5">
			<Eyebrow>{m.label}</Eyebrow>
			<Stat value={m.value} size="sm" tone={toneFor(m.tone) as any} />
		</div>
	{/each}
</div>
