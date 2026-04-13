<script lang="ts">
	import type { Snippet } from 'svelte';
	import '../app.css';
	import ThemeProvider from '$lib/theme/theme-provider.svelte';
	import { AppShell } from '$lib/chrome';

	interface Props {
		children: Snippet;
	}

	let { children }: Props = $props();
</script>

<ThemeProvider>
	<AppShell>
		{@render children()}
	</AppShell>
</ThemeProvider>
