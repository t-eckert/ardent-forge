<script lang="ts">
	import { ThreadsView } from '$lib/threads';
	import { makeThreadList, makeRenameThread } from '$lib/mocks';

	// Expose the rename thread alongside the default list so it's routable to /threads/thread-rename-t-client
	const threads = [makeRenameThread(), ...makeThreadList()];
</script>

<ThreadsView {threads} />
