<script lang="ts">
	import { FieldDetail, HealthWorkouts } from '$lib/fields';
	import { Display, Body } from '$lib/typography';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

{#if !data.field}
	<div class="p-12 flex flex-col gap-3">
		<Display size="md">Field not found</Display>
		<Body muted>No field found for this slug.</Body>
	</div>
{:else if data.field.slug === 'health'}
	<HealthWorkouts />
{:else}
	<FieldDetail field={data.field as import('$lib/schemas/field').Field} />
{/if}
