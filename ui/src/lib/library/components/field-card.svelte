<script lang="ts">
	import type { Field } from '$lib/schemas/field';
	import { Card } from '$lib/components';
	import { Display, Body, Eyebrow, Meta, Stat } from '$lib/typography';

	interface Props {
		field: Field;
	}

	let { field }: Props = $props();

	const statusToneClass = $derived(
		{
			ember: 'text-[var(--color-ember-deep)]',
			moss: 'text-[var(--color-moss)]',
			graphite: 'text-[var(--color-graphite)]',
			warn: 'text-[var(--color-warn)]'
		}[field.status.tone]
	);
</script>

<a href="/library/fields/{field.slug}" class="block">
	<Card
		surface={field.featured ? 'paper' : 'paper'}
		class={field.featured
			? 'bg-gradient-to-br from-[#FAF7F1] to-[#FDECE4] transition-colors hover:border-[var(--color-stone)]'
			: 'transition-colors hover:border-[var(--color-stone)]'}
	>
		<div class="flex flex-col gap-2.5 p-5">
			<div class="flex items-center justify-between">
				<Eyebrow tone={field.featured ? 'ember' : 'default'}>
					{field.name.toUpperCase()} · {field.category}
				</Eyebrow>
				<span class="font-mono text-[10px] {statusToneClass}">{field.status.label}</span>
			</div>
			<Display size="md">{field.name}</Display>
			<Body size="sm" muted>{field.tagline}</Body>
			<div class="flex gap-4 pt-1">
				{#each field.stats as stat (stat.label)}
					<div class="flex flex-col gap-0.5">
						<Eyebrow>{stat.label}</Eyebrow>
						<Stat value={stat.value} size="sm" />
					</div>
				{/each}
			</div>
		</div>
	</Card>
</a>
