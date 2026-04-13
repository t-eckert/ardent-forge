<script lang="ts">
	import { page } from '$app/state';
	import { FieldDetail, HealthWorkouts } from '$lib/fields';
	import { makeFields } from '$lib/mocks';
	import { Display, Body } from '$lib/typography';

	const fields = makeFields();
	const active = $derived(fields.find((f) => f.slug === page.params.slug));
</script>

{#if !active}
	<div class="p-12 flex flex-col gap-3">
		<Display size="md">Field not found</Display>
		<Body muted>No mock field has slug <span class="font-mono">{page.params.slug}</span>.</Body>
	</div>
{:else if active.slug === 'health'}
	<HealthWorkouts />
{:else}
	<FieldDetail field={active} />
{/if}
