<script lang="ts">
	import type { Field } from '$lib/schemas/field';
	import FieldShell from '../components/field-shell.svelte';
	import { Card } from '$lib/components';
	import { Body, Eyebrow, Meta } from '$lib/typography';

	interface Props {
		field: Field;
	}

	let { field }: Props = $props();
</script>

<FieldShell {field}>
	<Card surface="paper">
		<div class="flex flex-col gap-2.5 p-6">
			<Eyebrow>PLACEHOLDER</Eyebrow>
			<Body>
				This field doesn't have a specialised view yet. Build <span class="font-mono"
					>src/lib/fields/{field.slug}/</span
				> to add one.
			</Body>
			<Meta size="xs">Sources: {field.sources.join(' · ')}</Meta>
		</div>
	</Card>
</FieldShell>
