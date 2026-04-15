<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import Sidebar from '../components/sidebar.svelte';
	import BreadcrumbStrip from '../components/breadcrumb-strip.svelte';
	import { chromeState } from '../state/chrome.state.svelte';
	import { PaletteOverlay, mountPaletteKeybinding } from '$lib/palette';
	import { MOCK_RESULTS } from '$lib/palette/_stories/mock-data';

	interface ChromeCounts {
		threadCount?: number;
		tasksActive?: number;
		libraryCount?: number;
	}

	interface Props {
		children: Snippet;
		chrome?: ChromeCounts;
	}

	let { children, chrome = {} }: Props = $props();

	const path = $derived(page.url?.pathname ?? '/');
	const activeSpine = $derived(chromeState.spineFor(path));
	const trail = $derived(chromeState.breadcrumbFor(path));

	$effect(() => {
		const off = mountPaletteKeybinding();
		return off;
	});
</script>

<div class="flex min-h-screen bg-[var(--color-paper)]">
	<Sidebar
		active={activeSpine}
		threadCount={chrome.threadCount ?? 0}
		tasksActive={chrome.tasksActive ?? 0}
		libraryCount={chrome.libraryCount ?? 0}
	/>
	<main class="flex-1 flex flex-col min-w-0">
		<BreadcrumbStrip {trail} />
		<div class="flex-1">
			{@render children()}
		</div>
	</main>
</div>

<PaletteOverlay results={MOCK_RESULTS} />
