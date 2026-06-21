<script lang="ts">
	import { invalidateAll, goto } from '$app/navigation';
	import type { Task } from '$lib/schemas/task';
	import { api, ApiError } from '$lib/api/typed';
	import { Button } from '$lib/components';
	import { Meta } from '$lib/typography';

	interface Props {
		task: Task;
	}

	let { task }: Props = $props();

	const ACTIVE = new Set(['queued', 'triaging', 'executing', 'verifying', 'delivering']);
	const isActive = $derived(ACTIVE.has(task.status));
	const isCode = $derived(task.type === 'code');
	const canFollowUp = $derived(
		isCode && ['completed', 'failed', 'awaiting_approval'].includes(task.status)
	);
	const session = $derived((task.handler_data?.zellij_session as string | undefined) ?? undefined);

	let busy = $state(false);
	let error = $state<string | null>(null);
	let confirming = $state<null | 'cancel' | 'reject'>(null);
	let confirmTimer: ReturnType<typeof setTimeout> | undefined;
	let showFollowUp = $state(false);
	let followUpPrompt = $state('');
	let copied = $state(false);

	async function run(fn: () => Promise<unknown>) {
		if (busy) return;
		busy = true;
		error = null;
		try {
			await fn();
			await invalidateAll();
		} catch (e) {
			error = e instanceof ApiError || e instanceof Error ? e.message : 'Action failed';
		} finally {
			busy = false;
		}
	}

	function arm(which: 'cancel' | 'reject') {
		if (confirming === which) {
			clearTimeout(confirmTimer);
			confirming = null;
			run(() => (which === 'cancel' ? api.tasks.cancel(task.id) : api.tasks.reject(task.id)));
			return;
		}
		confirming = which;
		clearTimeout(confirmTimer);
		confirmTimer = setTimeout(() => (confirming = null), 3000);
	}

	async function submitFollowUp() {
		const prompt = followUpPrompt.trim();
		if (!prompt || busy) return;
		busy = true;
		error = null;
		try {
			const created = await api.tasks.followUp(task.id, prompt);
			await goto(`/tasks/${created.id}`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Follow-up failed';
		} finally {
			busy = false;
		}
	}

	async function copyAttach() {
		const cmd =
			(task.handler_data?.attach_cmd as string | undefined) ??
			(session ? `ssh box -t zellij attach ${session}` : '');
		if (!cmd) return;
		try {
			await navigator.clipboard.writeText(cmd);
			copied = true;
			setTimeout(() => (copied = false), 1500);
		} catch {
			error = 'Clipboard unavailable';
		}
	}
</script>

{#if task.status !== 'cancelled'}
	<div class="px-10 py-4 border-b border-[var(--color-border)] flex flex-col gap-3">
		<div class="flex flex-wrap items-center gap-2">
			{#if isActive}
				<Button variant="danger" size="sm" disabled={busy} onclick={() => arm('cancel')}>
					{confirming === 'cancel' ? 'Confirm?' : 'Cancel'}
				</Button>
			{/if}
			{#if task.status === 'awaiting_approval'}
				<Button
					variant="primary"
					size="sm"
					disabled={busy}
					onclick={() => run(() => api.tasks.approve(task.id))}>Approve</Button
				>
				<Button variant="danger" size="sm" disabled={busy} onclick={() => arm('reject')}>
					{confirming === 'reject' ? 'Confirm?' : 'Reject'}
				</Button>
			{/if}
			{#if task.status === 'failed'}
				<Button
					variant="secondary"
					size="sm"
					disabled={busy}
					onclick={() => run(() => api.tasks.retry(task.id))}>Retry</Button
				>
			{/if}
			{#if canFollowUp}
				<Button variant="secondary" size="sm" disabled={busy} onclick={() => (showFollowUp = !showFollowUp)}
					>Follow up</Button
				>
			{/if}
			{#if session}
				<Button variant="ghost" size="sm" onclick={copyAttach}
					>{copied ? 'Copied' : 'Copy attach cmd'}</Button
				>
			{/if}
		</div>

		{#if showFollowUp}
			<div
				class="flex flex-col gap-2 p-3 bg-[var(--color-bench)] border border-[var(--color-border)] rounded-[8px]"
			>
				<textarea
					bind:value={followUpPrompt}
					aria-label="Follow-up prompt"
					rows="3"
					placeholder="Describe the follow-up work — it continues the same session"
					class="w-full resize-none bg-transparent text-sm text-[var(--color-ink)] outline-none placeholder:text-[var(--color-graphite)]"
				></textarea>
				<div class="flex items-center gap-2 justify-end">
					<Button
						variant="ghost"
						size="sm"
						onclick={() => {
							showFollowUp = false;
							followUpPrompt = '';
						}}>Close</Button
					>
					<Button
						variant="primary"
						size="sm"
						disabled={busy || !followUpPrompt.trim()}
						onclick={submitFollowUp}>Send</Button
					>
				</div>
			</div>
		{/if}

		{#if error}
			<Meta size="xs">{error}</Meta>
		{/if}
	</div>
{/if}
