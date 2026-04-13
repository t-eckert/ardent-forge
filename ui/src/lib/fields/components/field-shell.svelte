<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { Field } from '$lib/schemas/field';
	import { Display, Body, Eyebrow } from '$lib/typography';

	interface Props {
		field: Field;
		children: Snippet;
	}

	let { field, children }: Props = $props();
</script>

<div class="flex flex-col gap-7 px-14 py-9 max-w-[1440px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>FIELD · {field.name.toUpperCase()}</Eyebrow>
		<Display size="xl">{field.name}</Display>
		<Body size="lg" class="font-display italic text-[var(--color-slate)]">{field.tagline}</Body>
	</div>
	{@render children()}
</div>
