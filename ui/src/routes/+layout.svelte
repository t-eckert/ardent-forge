<script lang="ts">
	import type { Snippet } from 'svelte';
	import '../app.css';
	import ThemeProvider from '$lib/theme/theme-provider.svelte';

	interface Props {
		children: Snippet;
	}

	let { children }: Props = $props();
</script>

<ThemeProvider>
	<!-- AppShell (chrome: sidebar + breadcrumb + palette host) lands in Phase 2. -->
	<div class="min-h-screen bg-[var(--color-paper)] text-[var(--color-ink)]">
		{@render children()}
	</div>
</ThemeProvider>
