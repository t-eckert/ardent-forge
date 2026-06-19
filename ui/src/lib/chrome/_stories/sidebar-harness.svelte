<script lang="ts">
	import Sidebar from '../components/sidebar.svelte';
	import type { Spine } from '../state/chrome.state.svelte';

	interface Props {
		active: Spine | null;
		tasksActive?: number;
	}

	let { active, tasksActive = 3 }: Props = $props();
</script>

<div class="flex min-h-screen bg-[var(--color-paper)]">
	<Sidebar {active} {tasksActive} />
	<main class="flex-1 p-8">
		<div class="font-mono text-xs tracking-wider text-[var(--color-graphite)]">
			· content area ·
		</div>
	</main>
</div>
