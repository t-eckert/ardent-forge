<script lang="ts">
	import SpineItem from './spine-item.svelte';
	import { Sun, ChatCircle, GitBranch, ListChecks, Gear, Robot, Brain, Plug, CalendarBlank, Receipt } from '$lib/icons';
	import { Meta, Eyebrow } from '$lib/typography';
	import { StatusDot, KeycapHint } from '$lib/components';
	import type { Spine } from '$lib/chrome/state/chrome.state.svelte';
	import { pinned } from '$lib/stores/pinned.state.svelte';
	import { sync } from '$lib/stores/sync.state.svelte';
	import { formatRelative } from '$lib/utils/date';

	interface Props {
		active: Spine | null;
		/** ISO date string; when set, the current day's abbreviation is shown next to Today */
		todayDow?: string;
		/** Unread thread count */
		threadCount?: number;
		/** Active-task count (running, queued, needs-review) */
		tasksActive?: number;
	}

	let {
		active,
		todayDow = new Date().toLocaleDateString('en-CA', { weekday: 'short' }).toUpperCase(),
		threadCount = 0,
		tasksActive = 0
	}: Props = $props();

	const syncTone = $derived(
		sync.overall === 'failing' ? 'warn' : sync.overall === 'stale' ? 'warn' : 'moss'
	);
</script>

<aside
	class="flex flex-col w-[220px] min-h-screen bg-[var(--color-bench)] border-r border-[var(--color-border)] px-3.5 py-5 gap-0.5"
>
	<!-- Brand -->
	<div class="flex items-center gap-2.5 px-1.5 pb-[18px]">
		<div
			class="flex items-center justify-center w-6 h-6 bg-[var(--color-ink)] text-[var(--color-paper)] font-display text-[15px] rounded-[3px]"
		>
			A
		</div>
		<span class="text-sm font-medium">Ardent Forge</span>
	</div>

	<!-- Spine -->
	<SpineItem href="/today" label="Today" icon={Sun} active={active === 'today'}>
		{#snippet meta()}
			<Meta size="xs">{todayDow}</Meta>
		{/snippet}
	</SpineItem>
	<SpineItem href="/threads" label="Threads" icon={ChatCircle} active={active === 'threads'}>
		{#snippet meta()}
			<Meta size="xs">{threadCount || ''}</Meta>
		{/snippet}
	</SpineItem>
	<SpineItem href="/repos" label="Repos" icon={GitBranch} active={active === 'repos'} />
	<SpineItem href="/tasks" label="Tasks" icon={ListChecks} active={active === 'tasks'}>
		{#snippet meta()}
			{#if tasksActive > 0}
				<span class="inline-flex items-center gap-1">
					<StatusDot tone="moss" />
					<Meta size="xs">{tasksActive}</Meta>
				</span>
			{/if}
		{/snippet}
	</SpineItem>

	<!-- System -->
	<div class="pt-4 pb-1 px-2.5">
		<Eyebrow>SYSTEM</Eyebrow>
	</div>
	<SpineItem href="/library/agents" label="Agents" icon={Robot} active={active === 'agents'} />
	<SpineItem href="/library/connectors" label="Connectors" icon={Plug} active={active === 'connectors'} />
	<SpineItem href="/library/schedules" label="Schedules" icon={CalendarBlank} active={active === 'schedules'} />
	<SpineItem href="/library/memory" label="Memory" icon={Brain} active={active === 'memory'} />
	<SpineItem href="/library/log" label="Log" icon={Receipt} active={active === 'log'} />

	<!-- Pinned -->
	{#if pinned.items.length > 0}
		<div class="pt-5 pb-1.5 px-2.5">
			<Eyebrow>PINNED</Eyebrow>
		</div>
		{#each pinned.items as item (item.id)}
			<a
				href={item.href}
				class="flex items-center gap-2 px-2.5 py-1.5 text-[12px] text-[var(--color-slate)] hover:bg-[var(--color-paper)]/60 rounded"
			>
				<span class="font-mono text-[var(--color-graphite)]">◆</span>
				<span class="truncate">{item.label}</span>
			</a>
		{/each}
	{/if}

	<!-- Footer: settings + ⌘K + sync -->
	<div class="mt-auto pt-2.5 border-t border-[var(--color-border)]">
		<a
			href="/settings"
			class="flex items-center gap-2 px-2.5 py-1.5 text-[12px] text-[var(--color-slate)] hover:bg-[var(--color-paper)]/60 rounded"
		>
			<Gear size={14} weight="regular" />
			<span>Settings</span>
		</a>
		<div class="flex items-center justify-between px-2.5 py-1">
			<Meta size="xs">Quick find</Meta>
			<KeycapHint keys={['⌘', 'K']} />
		</div>
		<div class="flex items-center gap-1.5 px-2.5 py-1.5">
			<StatusDot tone={syncTone} />
			<Meta size="xs">
				{#if sync.lastSyncIso}
					synced · {formatRelative(sync.lastSyncIso)}
				{:else}
					no sources
				{/if}
			</Meta>
		</div>
	</div>
</aside>
