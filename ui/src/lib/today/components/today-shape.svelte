<script lang="ts">
	import { Heading, Meta } from '$lib/typography';
	import { Chip } from '$lib/components';

	interface TimelineItem {
		time: string;
		title: string;
		note: string;
		tag?: { label: string; tone?: 'ember' | 'neutral' | 'moss' };
		highlight?: boolean;
	}

	interface Props {
		items: TimelineItem[];
		label?: string;
		rangeLabel?: string;
	}

	let {
		items,
		label = "Today's shape",
		rangeLabel = '08:00 – 20:00'
	}: Props = $props();
</script>

<section class="flex flex-col gap-3">
	<header class="flex items-end justify-between pb-1.5 border-b border-[var(--color-border)]">
		<div class="flex items-baseline gap-2.5">
			<Heading size="md">{label}</Heading>
			<Meta size="sm">{rangeLabel}</Meta>
		</div>
		<a href="/library/schedule" class="font-mono text-[11px] text-[var(--color-ember-deep)]">
			open schedule →
		</a>
	</header>
	<div class="flex flex-col">
		{#each items as item, i (i)}
			<div
				class="flex items-start py-2.5"
				class:border-b={i < items.length - 1}
				style={i < items.length - 1 ? 'border-color: var(--color-border)' : ''}
			>
				<span
					class="w-[70px] font-mono text-[12px] flex-shrink-0"
					style="color: {item.highlight ? 'var(--color-ember-deep)' : 'var(--color-graphite)'};"
				>
					{item.time}
				</span>
				<div class="flex flex-col gap-0.5 flex-1 min-w-0">
					<div class="flex items-center gap-2 flex-wrap">
						<span class="text-sm text-[var(--color-ink)]">{item.title}</span>
						{#if item.tag}
							<Chip tone={item.tag.tone ?? 'neutral'}>{item.tag.label}</Chip>
						{/if}
					</div>
					<Meta size="xs">{item.note}</Meta>
				</div>
			</div>
		{/each}
	</div>
</section>
