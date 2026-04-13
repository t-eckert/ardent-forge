<script lang="ts">
	import CodeDiff from '../code-diff/code-diff.svelte';
	import type { CodeDiffPayload } from '$lib/schemas/widgets/code-diff';

	interface Props {
		payload: CodeDiffPayload;
	}

	let { payload }: Props = $props();
</script>

<div class="min-h-screen bg-[var(--color-paper)] p-8">
	<CodeDiff {payload} />
</div>
