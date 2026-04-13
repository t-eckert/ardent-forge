<script lang="ts">
	import type { WidgetPayload } from '$lib/schemas/widgets';
	import WidgetHost from '../kernel/widget-host.svelte';

	interface Props {
		payload: WidgetPayload;
	}
	let { payload }: Props = $props();
</script>

<div class="min-h-screen bg-[var(--color-paper)] p-8">
	<WidgetHost {payload} />
</div>
