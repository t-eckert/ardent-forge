<script lang="ts">
	import ThreadView from '../views/thread-view.svelte';
	import { makeRenameThread, makeThreadList } from '$lib/mocks';

	const rename = makeRenameThread();
	const threads = [rename, ...makeThreadList()];
</script>

<div class="min-h-screen bg-[var(--color-paper)]">
	<ThreadView {threads} active={rename} />
</div>
