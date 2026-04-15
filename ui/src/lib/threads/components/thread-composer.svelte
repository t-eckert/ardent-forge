<script lang="ts">
	import { Meta } from '$lib/typography';
	import { Chip, KeycapHint } from '$lib/components';

	interface Props {
		scopeChips?: string[];
		modelLabel?: string;
		placeholder?: string;
		disabled?: boolean;
		onsubmit?: (content: string) => void | Promise<void>;
	}

	let {
		scopeChips = ['@thread', '@today', '/tools'],
		modelLabel = 'claude-opus-4-6 · code+tools',
		placeholder = 'Continue the thread…',
		disabled = false,
		onsubmit
	}: Props = $props();

	let value = $state('');
	let sending = $state(false);
	let textarea: HTMLTextAreaElement | undefined = $state();

	function resize() {
		if (!textarea) return;
		textarea.style.height = 'auto';
		textarea.style.height = Math.min(textarea.scrollHeight, 160) + 'px';
	}

	async function submit() {
		const content = value.trim();
		if (!content || sending || disabled || !onsubmit) return;
		sending = true;
		try {
			await onsubmit(content);
			value = '';
			if (textarea) {
				textarea.style.height = 'auto';
			}
		} finally {
			sending = false;
		}
	}

	function onkey(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			submit();
		}
	}
</script>

<div
	class="flex flex-col gap-2.5 p-4 bg-[var(--color-bench)] border-t border-[var(--color-border)]"
>
	<div class="flex items-center justify-between">
		<div class="flex gap-1.5">
			{#each scopeChips as chip (chip)}
				<Chip tone="outline">{chip}</Chip>
			{/each}
		</div>
		<Meta size="sm">{modelLabel}</Meta>
	</div>
	<div
		class="flex items-end gap-2.5 px-3 py-2.5 bg-[var(--color-paper)] border border-[var(--color-stone)] rounded-md"
	>
		<textarea
			bind:this={textarea}
			bind:value
			{placeholder}
			disabled={disabled || sending}
			onkeydown={onkey}
			oninput={resize}
			rows={1}
			class="flex-1 bg-transparent text-sm text-[var(--color-ink)] placeholder:text-[var(--color-graphite)] outline-none resize-none leading-snug"
			style="height: auto; max-height: 160px;"
			aria-label="Message"
		></textarea>
		<KeycapHint keys={['↵']} />
	</div>
</div>
