<script lang="ts">
	import type { CodeDiffPayload } from '$lib/schemas/widgets/code-diff';
	import WidgetShell from '../components/widget-shell.svelte';
	import { Code } from '$lib/icons';
	import { Button } from '$lib/components';
	import { Meta } from '$lib/typography';

	interface Props {
		payload: CodeDiffPayload;
		onAction?: (kind: CodeDiffPayload['actions'][number]['kind']) => void;
	}

	let { payload, onAction }: Props = $props();

	// Primary action is the last one in the list by convention
	const primaryIdx = $derived(payload.actions.length - 1);
</script>

<WidgetShell
	toolId="code.diff"
	badgeIcon={Code}
	badgeTone="ink"
	context={payload.context}
	footerMeta={`branch: ${payload.branch}${payload.footerMeta ? ` · ${payload.footerMeta}` : ''}`}
>
	{#snippet headerMeta()}
		<span class="inline-flex items-baseline gap-1">
			<span class="font-mono text-[11px] text-[var(--color-moss)]">+{payload.additions}</span>
			<span class="font-mono text-[11px] text-[var(--color-ember-deep)]">−{payload.deletions}</span>
		</span>
		<Meta size="sm">{payload.files.length} files</Meta>
	{/snippet}

	{#snippet body()}
		{#each payload.files as file, i (file.path)}
			<div
				class="flex items-center justify-between px-4 py-2.5 border-b border-[var(--color-border)]"
			>
				<div class="flex items-center gap-2.5 min-w-0">
					<span class="font-mono text-[12px] text-[var(--color-ink)] truncate">{file.path}</span>
					<Meta size="xs">{file.changes} {file.changes === 1 ? 'change' : 'changes'}</Meta>
				</div>
				<span class="inline-flex items-baseline gap-1 flex-shrink-0">
					<span class="font-mono text-[10px] text-[var(--color-moss)]">+{file.additions}</span>
					<span class="font-mono text-[10px] text-[var(--color-ember-deep)]">−{file.deletions}</span>
				</span>
			</div>

			{#if file.hunk && i === 0}
				<div class="flex flex-col py-2 bg-[var(--color-paper)]">
					{#each file.hunk.lines as line, j (j)}
						<div
							class="flex items-start"
							style="background: {line.kind === 'add'
								? '#E7F1E6'
								: line.kind === 'remove'
									? '#FDECE4'
									: 'transparent'};"
						>
							<span
								class="w-[48px] text-right pr-3 font-mono text-[11px] flex-shrink-0 py-[2px]"
								style="color: {line.kind === 'add'
									? 'var(--color-moss)'
									: line.kind === 'remove'
										? 'var(--color-ember-deep)'
										: 'var(--color-graphite)'};"
							>
								{line.line}
							</span>
							<span
								class="w-[16px] font-mono text-[11px] flex-shrink-0 py-[2px]"
								style="color: {line.kind === 'add'
									? 'var(--color-moss)'
									: line.kind === 'remove'
										? 'var(--color-ember-deep)'
										: 'transparent'};"
							>
								{line.kind === 'add' ? '+' : line.kind === 'remove' ? '−' : ' '}
							</span>
							<span
								class="flex-1 font-mono text-[12px] text-[var(--color-ink)] whitespace-pre py-[2px]"
								>{line.content}</span
							>
						</div>
					{/each}
				</div>
			{/if}
		{/each}
	{/snippet}

	{#snippet actions()}
		{#each payload.actions as action, i (action.kind)}
			<Button
				variant={i === primaryIdx ? 'primary' : 'secondary'}
				size="sm"
				onclick={() => onAction?.(action.kind)}
			>
				{action.label}
			</Button>
		{/each}
	{/snippet}
</WidgetShell>
