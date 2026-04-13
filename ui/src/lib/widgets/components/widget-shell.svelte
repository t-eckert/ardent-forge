<script lang="ts">
	import type { Snippet, Component } from 'svelte';
	import { Meta } from '$lib/typography';
	import { cn } from '$lib/utils/cn';

	/**
	 * Shared chrome for every chat widget: eyebrow tool badge + contextual query
	 * in the header, arbitrary body, optional footer with meta + actions.
	 *
	 * All built-in widgets wrap this so they look like a family. If your widget
	 * needs a different shape, it doesn't belong as a widget yet.
	 */

	interface Props {
		/** Tool id (e.g. 'code.diff', 'health.workouts'), shown as CODE.DIFF */
		toolId: string;
		/** Icon component for the tool badge */
		badgeIcon: Component;
		/** Background colour for the badge pill */
		badgeTone?: 'ink' | 'ember' | 'signal' | 'graphite' | 'warn' | 'moss';
		/** Contextual query/subject rendered after the tool badge */
		context: string;
		/** Right-side meta shown in the header (e.g. "+14 −14 · 4 files") */
		headerMeta?: Snippet;
		/** The widget body */
		body: Snippet;
		/** Footer meta — status line, source attribution, etc. */
		footerMeta?: string;
		/** Footer actions — typically 1–3 buttons */
		actions?: Snippet;
		class?: string;
	}

	let {
		toolId,
		badgeIcon: BadgeIcon,
		badgeTone = 'ink',
		context,
		headerMeta,
		body,
		footerMeta,
		actions,
		class: klass
	}: Props = $props();

	const badgeBg = $derived(
		{
			ink: 'var(--color-ink)',
			ember: 'var(--color-ember)',
			signal: 'var(--color-signal)',
			graphite: 'var(--color-graphite)',
			warn: 'var(--color-warn)',
			moss: 'var(--color-moss)'
		}[badgeTone]
	);
</script>

<article
	class={cn(
		'flex flex-col max-w-[980px] bg-[var(--color-paper)] border border-[var(--color-border)] rounded-[8px] overflow-hidden',
		klass
	)}
>
	<header
		class="flex items-center justify-between px-4 py-3 bg-[var(--color-bench)] border-b border-[var(--color-border)] gap-3"
	>
		<div class="flex items-center gap-2.5 min-w-0">
			<span
				class="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[4px] text-[var(--color-paper)] flex-shrink-0"
				style="background: {badgeBg};"
			>
				<BadgeIcon size={12} weight="regular" />
			</span>
			<Meta size="sm">{toolId.toUpperCase()}</Meta>
			<span class="font-mono text-[11px] text-[var(--color-ink)] truncate">{context}</span>
		</div>
		{#if headerMeta}
			<div class="flex items-center gap-3 flex-shrink-0">
				{@render headerMeta()}
			</div>
		{/if}
	</header>

	<div class="flex flex-col">
		{@render body()}
	</div>

	{#if actions || footerMeta}
		<footer
			class="flex items-center justify-between px-4 py-3 bg-[var(--color-bench)] border-t border-[var(--color-border)] gap-3"
		>
			{#if footerMeta}
				<Meta size="sm">{footerMeta}</Meta>
			{:else}
				<span></span>
			{/if}
			{#if actions}
				<div class="flex items-center gap-2">
					{@render actions()}
				</div>
			{/if}
		</footer>
	{/if}
</article>
