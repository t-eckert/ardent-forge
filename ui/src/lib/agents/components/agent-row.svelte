<script lang="ts">
	import type { AgentRun } from '$lib/schemas/agent';
	import { Avatar, Chip } from '$lib/components';
	import { Meta } from '$lib/typography';
	import { formatTime } from '$lib/utils/date';

	interface Props {
		run: AgentRun;
		active?: boolean;
		/** Where clicking the row should navigate */
		href?: string;
	}

	let { run, active = false, href }: Props = $props();

	const badge = $derived(badgeFor(run.kind));
	const chip = $derived(chipFor(run.status));

	function badgeFor(kind: AgentRun['kind']): { label: string; tone: 'ink' | 'signal' | 'graphite' | 'ember' | 'warn' } {
		switch (kind) {
			case 'code-agent':
				return { label: '{}', tone: 'ink' };
			case 'triage-agent':
				return { label: '⟲', tone: 'signal' };
			case 'notebook-sync':
				return { label: '¶', tone: 'graphite' };
			case 'strava-pull':
				return { label: '♥', tone: 'ember' };
			case 'ci-watcher':
				return { label: '▸', tone: 'ink' };
			case 'backup-agent':
				return { label: '!', tone: 'warn' };
			default:
				return { label: '·', tone: 'ink' };
		}
	}

	function chipFor(status: AgentRun['status']): { label: string; tone: 'ember' | 'moss' | 'neutral' } {
		switch (status) {
			case 'running':
				return { label: 'running', tone: 'ember' };
			case 'needs-review':
				return { label: 'needs review', tone: 'ember' };
			case 'done':
				return { label: 'done', tone: 'moss' };
			case 'failed':
				return { label: 'failed', tone: 'ember' };
			case 'cron':
				return { label: 'cron', tone: 'moss' };
			case 'watching':
				return { label: 'watching', tone: 'moss' };
		}
	}

	const displayTime = $derived(
		run.status === 'cron' || run.status === 'watching' ? run.durationLabel : `${formatTime(run.startedIso)} · ${run.durationLabel}`
	);
</script>

<a
	href={href ?? '#'}
	class="flex flex-col gap-1.5 px-5 py-3.5 border-b border-[var(--color-border)] transition-colors"
	style={active
		? 'background: var(--color-bench); border-left: 2px solid var(--color-ember);'
		: ''}
>
	<div class="flex items-center justify-between">
		<div class="flex items-center gap-2">
			<Avatar label={badge.label} tone={badge.tone} size="sm" />
			<span
				class="text-[13px]"
				class:font-medium={active}
				style="color: {active ? 'var(--color-ink)' : 'var(--color-slate)'};"
			>
				{run.kind}
			</span>
		</div>
		<Chip tone={chip.tone}>{chip.label}</Chip>
	</div>
	<Meta size="sm">{run.id} · {displayTime}</Meta>
	<span class="text-[12px] text-[var(--color-slate)]">{run.summary}</span>
</a>
