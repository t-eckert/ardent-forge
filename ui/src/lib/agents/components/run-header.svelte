<script lang="ts">
	import type { AgentRunDetail } from '$lib/schemas/agent';
	import { Display, Body, Eyebrow } from '$lib/typography';

	interface Props {
		run: AgentRunDetail;
	}

	let { run }: Props = $props();
</script>

<header class="flex flex-col gap-1.5">
	<Eyebrow>TRIGGER · {run.triggerNote}</Eyebrow>
	<Display size="md">{run.title}</Display>
	<Body size="sm" muted>
		Queued by {run.queuedBy} · <span class="font-mono">{run.runtime}</span>
	</Body>
</header>
