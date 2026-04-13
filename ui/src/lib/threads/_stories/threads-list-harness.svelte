<script lang="ts">
	import ThreadsView from '../views/threads-view.svelte';
	import { makeRenameThread, makeThreadList } from '$lib/mocks';

	const threads = [makeRenameThread(), ...makeThreadList()];
</script>

<div class="min-h-screen bg-[var(--color-paper)]">
	<ThreadsView {threads} />
</div>
