<script lang="ts">
	import Sidebar from '../components/sidebar.svelte';
	import type { Spine } from '../state/chrome.state.svelte';

	interface Props {
		active: Spine | null;
		threadCount?: number;
		libraryCount?: number;
		agentsRunning?: number;
	}

	let { active, threadCount = 12, libraryCount = 1412, agentsRunning = 3 }: Props = $props();
</script>

<div class="flex min-h-screen bg-[var(--color-paper)]">
	<Sidebar {active} {threadCount} {libraryCount} {agentsRunning} />
	<main class="flex-1 p-8">
		<div class="font-mono text-xs tracking-wider text-[var(--color-graphite)]">
			· content area ·
		</div>
	</main>
</div>
