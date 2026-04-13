<script lang="ts">
	import { Display, Body, Heading, Eyebrow } from '$lib/typography';
	import { Card } from '$lib/components';

	const facets = [
		{ label: 'Fields', href: '/library/fields', count: '7' },
		{ label: 'Daily log', href: '/library/log', count: '1,412' },
		{ label: 'Tasks', href: '/library/tasks', count: '24' },
		{ label: 'Schedule', href: '/library/schedule', count: '—' },
		{ label: 'People', href: '/library/people', count: '204' },
		{ label: 'Wiki', href: '/library/wiki', count: '218' },
		{ label: 'Collections', href: '/library/collections', count: '7' }
	];
</script>

<div class="flex flex-col gap-8 px-14 py-9 max-w-[1200px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>LIBRARY</Eyebrow>
		<Display size="lg">Library</Display>
		<Heading size="sm" italic>Everything structured — fields, logs, tasks, people, wiki.</Heading>
	</div>

	<div class="grid grid-cols-2 gap-4">
		{#each facets as f (f.label)}
			<a href={f.href}>
				<Card surface="paper" class="transition-colors hover:border-[var(--color-stone)]">
					<div class="flex items-center justify-between p-5">
						<Heading size="sm">{f.label}</Heading>
						<span class="font-mono text-[var(--color-graphite)]">{f.count}</span>
					</div>
				</Card>
			</a>
		{/each}
	</div>
</div>
