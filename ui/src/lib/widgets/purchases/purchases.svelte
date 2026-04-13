<script lang="ts">
	import type { PurchasesPayload } from '$lib/schemas/widgets/purchases';
	import WidgetShell from '../components/widget-shell.svelte';
	import { Receipt } from '$lib/icons';
	import { Meta, Stat, Eyebrow } from '$lib/typography';

	interface Props {
		payload: PurchasesPayload;
	}

	let { payload }: Props = $props();
</script>

<WidgetShell
	toolId="finance.purchases"
	badgeIcon={Receipt}
	badgeTone="signal"
	context={payload.rangeLabel}
>
	{#snippet headerMeta()}
		<div class="flex flex-col items-end gap-0.5">
			<Eyebrow>TOTAL</Eyebrow>
			<Stat value={payload.totalLabel} size="md" />
		</div>
	{/snippet}

	{#snippet body()}
		<div class="grid grid-cols-[70px_1fr_110px_100px] px-4 py-2 border-b border-[var(--color-border)] font-mono text-[10px] tracking-wider text-[var(--color-graphite)]">
			<span>DATE</span><span>MERCHANT</span><span>CATEGORY</span><span class="text-right">AMOUNT</span>
		</div>
		{#each payload.rows as row, i (i)}
			<div
				class="grid grid-cols-[70px_1fr_110px_100px] items-center px-4 py-2 text-[13px]"
				class:border-b={i < payload.rows.length - 1}
				style={i < payload.rows.length - 1 ? 'border-color: var(--color-border)' : ''}
			>
				<span class="font-mono text-[12px] text-[var(--color-graphite)]">{row.dateLabel}</span>
				<span class="text-[var(--color-ink)]">{row.merchant}</span>
				<Meta size="xs">{row.category}</Meta>
				<span class="font-mono text-[13px] text-right">{row.amountLabel}</span>
			</div>
		{/each}
	{/snippet}
</WidgetShell>
