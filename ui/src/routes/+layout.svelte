<script lang="ts">
	import type { Snippet } from 'svelte';
	import '../app.css';
	import ThemeProvider from '$lib/theme/theme-provider.svelte';
	import { AppShell } from '$lib/chrome';
	import type { LayoutData } from './$types';

	interface Props {
		children: Snippet;
		data: LayoutData;
	}

	let { children, data }: Props = $props();
</script>

<svelte:head>
	<title>Ardent Forge</title>
</svelte:head>

<ThemeProvider>
	<AppShell chrome={data.chrome}>
		{@render children()}
	</AppShell>
</ThemeProvider>
