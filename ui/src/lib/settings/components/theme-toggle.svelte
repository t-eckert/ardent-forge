<script lang="ts">
	import { getThemeStore, type Theme } from '$lib/theme/theme-store.svelte';

	const theme = getThemeStore();

	const options: { value: Theme; label: string }[] = [
		{ value: 'light', label: 'Light' },
		{ value: 'dark', label: 'Dark' },
		{ value: 'system', label: 'System' }
	];
</script>

<div
	class="inline-flex rounded-md border border-[var(--color-stone)] bg-[var(--color-paper)] p-0.5"
	role="radiogroup"
	aria-label="Theme"
>
	{#each options as option (option.value)}
		{@const active = theme.preference === option.value}
		<button
			type="button"
			role="radio"
			aria-checked={active}
			onclick={() => theme.setTheme(option.value)}
			class="px-3 h-7 text-[12px] font-sans rounded-[5px] transition-colors {active
				? 'bg-[var(--color-ink)] text-[var(--color-paper)]'
				: 'text-[var(--color-slate)] hover:text-[var(--color-ink)]'}"
		>
			{option.label}
		</button>
	{/each}
</div>
