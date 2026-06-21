<script lang="ts">
	import type { Task } from '$lib/schemas/task';
	import { Avatar, Chip } from '$lib/components';
	import { Meta } from '$lib/typography';
	import { formatTime } from '$lib/utils/date';

	interface Props {
		task: Task;
		active?: boolean;
		href?: string;
	}

	let { task, active = false, href }: Props = $props();

	const badge = $derived(badgeFor(task.type));
	const chip = $derived(chipFor(task.status));

	function badgeFor(type: string): { label: string; tone: 'ink' | 'signal' | 'graphite' | 'ember' | 'warn' } {
		switch (type) {
			case 'code': return { label: '{}', tone: 'ink' };
			case 'plan': return { label: '◇', tone: 'signal' };
			case 'tickets': return { label: '#', tone: 'ember' };
			case 'echo': return { label: '·', tone: 'graphite' };
			default: return { label: '·', tone: 'graphite' };
		}
	}

	function chipFor(status: Task['status']): { label: string; tone: 'ember' | 'moss' | 'neutral' } {
		switch (status) {
			case 'queued': return { label: 'queued', tone: 'neutral' };
			case 'triaging': return { label: 'triaging', tone: 'ember' };
			case 'executing': return { label: 'executing', tone: 'ember' };
			case 'verifying': return { label: 'verifying', tone: 'ember' };
			case 'delivering': return { label: 'delivering', tone: 'ember' };
			case 'completed': return { label: 'done', tone: 'moss' };
			case 'failed': return { label: 'failed', tone: 'ember' };
			case 'awaiting_approval': return { label: 'awaiting approval', tone: 'neutral' };
			case 'cancelled': return { label: 'cancelled', tone: 'neutral' };
		}
	}
</script>

<a
	href={href ?? `/tasks/${task.id}`}
	class="flex flex-col gap-1.5 px-5 py-3.5 border-b border-[var(--color-border)] transition-colors"
	style={active ? 'background: var(--color-bench); border-left: 2px solid var(--color-ember);' : ''}
>
	<div class="flex items-center justify-between">
		<div class="flex items-center gap-2">
			<Avatar label={badge.label} tone={badge.tone} size="sm" />
			<span class="text-[13px]" class:font-medium={active}
				style="color: {active ? 'var(--color-ink)' : 'var(--color-slate)'};">
				{task.type}
			</span>
		</div>
		<Chip tone={chip.tone}>{chip.label}</Chip>
	</div>
	<Meta size="sm">{task.id.slice(0, 8)} · {formatTime(task.created_at)}</Meta>
	<span class="text-[12px] text-[var(--color-slate)] line-clamp-2">{task.title || task.description}</span>
</a>
