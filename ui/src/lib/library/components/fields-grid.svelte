<script lang="ts">
	import type { Field } from '$lib/schemas/field';
	import FieldCard from './field-card.svelte';
	import { Card } from '$lib/components';
	import { Eyebrow, Heading, Body } from '$lib/typography';
	import { Button } from '$lib/components';

	interface Props {
		fields: Field[];
	}

	let { fields }: Props = $props();
</script>

<div class="flex flex-col gap-4">
	<!-- Rows of 3 for the first two rows; last row mixes one field + new-field slot -->
	<div class="grid grid-cols-3 gap-4">
		{#each fields.slice(0, 6) as field (field.slug)}
			<FieldCard {field} />
		{/each}
	</div>
	<div class="grid grid-cols-3 gap-4">
		{#each fields.slice(6) as field (field.slug)}
			<FieldCard {field} />
		{/each}
		<div class="col-span-2">
			<Card surface="empty">
				<div class="flex flex-col gap-2.5 p-5">
					<Eyebrow>NEW FIELD</Eyebrow>
					<Heading size="sm" italic>
						A field is a life area with its own practice, people, and record. Add one when a topic
						outgrows the daily log.
					</Heading>
					<div class="flex gap-2 pt-1">
						<Button variant="primary" size="sm">+ New field</Button>
						<Button variant="secondary" size="sm">Import from Obsidian</Button>
					</div>
				</div>
			</Card>
		</div>
	</div>
</div>
