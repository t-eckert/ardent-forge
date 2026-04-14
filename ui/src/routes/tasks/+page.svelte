<script lang="ts">
	// Phase J (bespoke TaskListView) will replace this with a first-class
	// tasks UI. For now the AgentsListView is the best stand-in since the
	// agent-run flow is what the Tasks spine is a superset of.
	import { AgentsListView } from '$lib/agents';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

<AgentsListView runs={data.runs} />
