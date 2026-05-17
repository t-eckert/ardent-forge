<script lang="ts">
	import { GitBranch, GithubLogo } from 'phosphor-svelte';
	import type { CodeResultPayload } from '$lib/schemas/widgets';
	import WidgetShell from '../components/widget-shell.svelte';
	import { Body, Meta } from '$lib/typography';

	interface Props {
		payload: CodeResultPayload;
	}
	let { payload }: Props = $props();

	const LONG_OUTPUT_THRESHOLD = 400;
	let expandedOutput = $state(false);
</script>

<WidgetShell
	toolId="code.result"
	context={payload.branch ?? 'code change'}
	badgeIcon={GithubLogo}
	badgeTone="ink"
	footerMeta={payload.prUrl ? 'pull request opened' : 'branch pushed'}
>
	{#snippet body()}
		<div class="flex flex-col gap-3 px-4 py-3">
			{#if payload.summary}
				<Body>{payload.summary}</Body>
			{/if}
			{#if payload.prUrl}
				<a
					href={payload.prUrl}
					target="_blank"
					rel="noreferrer"
					class="inline-flex items-center gap-2 px-3 py-2 rounded-md bg-[var(--color-ink)] text-[var(--color-paper)] font-mono text-[12px] self-start hover:bg-[var(--color-graphite)] transition-colors"
				>
					<GithubLogo size={14} /> open pull request
				</a>
			{/if}
			{#if payload.branch}
				<div class="flex items-center gap-2">
					<GitBranch size={14} class="text-[var(--color-graphite)]" />
					<span class="font-mono text-[12px] text-[var(--color-slate)]">{payload.branch}</span>
				</div>
			{/if}
			{#if payload.claudeOutput}
				<div class="flex flex-col gap-1 pt-2 border-t border-[var(--color-border)]">
					<Meta size="sm">CLAUDE OUTPUT</Meta>
					<pre
						class="font-mono text-[11px] text-[var(--color-ink)] whitespace-pre-wrap break-words">{expandedOutput || payload.claudeOutput.length <= LONG_OUTPUT_THRESHOLD
							? payload.claudeOutput
							: payload.claudeOutput.slice(0, LONG_OUTPUT_THRESHOLD) + '…'}</pre>
					{#if payload.claudeOutput.length > LONG_OUTPUT_THRESHOLD}
						<button
							type="button"
							class="text-[11px] text-[var(--color-graphite)] underline cursor-pointer self-start"
							onclick={() => (expandedOutput = !expandedOutput)}
						>
							{expandedOutput ? 'show less' : `show more (${payload.claudeOutput.length} chars)`}
						</button>
					{/if}
				</div>
			{/if}
		</div>
	{/snippet}
</WidgetShell>
