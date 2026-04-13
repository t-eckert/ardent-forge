<script lang="ts">
	import type { WidgetPayload } from '$lib/schemas/widgets';
	import { WidgetHost } from '$lib/widgets';
	import { Eyebrow } from '$lib/typography';

	interface Props {
		/** Label rendered in the eyebrow, e.g. "ARTIFACT · PR #247" */
		label: string;
		payload: WidgetPayload;
	}

	let { label, payload }: Props = $props();
</script>

<section class="flex flex-col gap-2.5">
	<Eyebrow>ARTIFACT · {label}</Eyebrow>
	<WidgetHost {payload} />
</section>
