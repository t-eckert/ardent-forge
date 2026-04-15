<script lang="ts">
	import { Article } from 'phosphor-svelte';
	import type { ResultPayload } from '$lib/schemas/widgets';
	import WidgetShell from '../components/widget-shell.svelte';
	import { Meta } from '$lib/typography';

	interface Props {
		payload: ResultPayload;
	}
	let { payload }: Props = $props();

	const LONG_STRING_THRESHOLD = 400;

	let expanded = $state<Record<string, boolean>>({});

	function isUrl(v: unknown): v is string {
		return typeof v === 'string' && /^https?:\/\//i.test(v);
	}

	function formatValue(v: unknown): string {
		if (v === null || v === undefined) return '—';
		if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return String(v);
		return JSON.stringify(v);
	}

	const entries = $derived(Object.entries(payload.data ?? {}));
</script>

<WidgetShell
	toolId="result"
	context={payload.label}
	badgeIcon={Article}
	badgeTone="graphite"
	footerMeta={`${entries.length} field${entries.length === 1 ? '' : 's'}`}
>
	{#snippet body()}
		{#if entries.length === 0}
			<div class="px-4 py-3">
				<Meta size="sm">empty result</Meta>
			</div>
		{:else}
			<dl
				class="grid grid-cols-[180px_1fr] gap-x-4 gap-y-1 px-4 py-3 font-mono text-[12px] items-start"
			>
				{#each entries as [k, v] (k)}
					<dt class="text-[var(--color-slate)] truncate">{k}</dt>
					<dd class="text-[var(--color-ink)] break-words min-w-0">
						{#if isUrl(v)}
							<a
								class="underline text-[var(--color-signal)]"
								href={v}
								target="_blank"
								rel="noreferrer">{v}</a
							>
						{:else if Array.isArray(v)}
							{#if v.length === 0}
								<span class="text-[var(--color-graphite)]">[]</span>
							{:else}
								<ul class="flex flex-col gap-0.5">
									{#each v.slice(0, 10) as item, i (i)}
										<li>{formatValue(item)}</li>
									{/each}
									{#if v.length > 10}
										<li class="text-[var(--color-graphite)]">… {v.length - 10} more</li>
									{/if}
								</ul>
							{/if}
						{:else if typeof v === 'string' && v.length > LONG_STRING_THRESHOLD}
							<div>
								{expanded[k] ? v : v.slice(0, LONG_STRING_THRESHOLD) + '…'}
							</div>
							<button
								type="button"
								class="mt-1 text-[11px] text-[var(--color-graphite)] underline cursor-pointer"
								onclick={() => (expanded[k] = !expanded[k])}
							>
								{expanded[k] ? 'show less' : `show more (${v.length} chars)`}
							</button>
						{:else}
							{formatValue(v)}
						{/if}
					</dd>
				{/each}
			</dl>
		{/if}
	{/snippet}
</WidgetShell>
