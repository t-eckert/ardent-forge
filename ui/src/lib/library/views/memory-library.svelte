<script lang="ts">
	import { Display, Eyebrow, Heading, Meta, Body } from '$lib/typography';
	import { Card, Chip } from '$lib/components';

	interface MemoryEntry {
		filename: string;
		slug: string;
		name: string;
		description: string;
		type: 'user' | 'feedback' | 'project' | 'reference';
		body: string;
		updated_at?: string | null;
	}

	interface Props {
		entries: MemoryEntry[];
	}

	let { entries }: Props = $props();

	type Type = 'user' | 'feedback' | 'project' | 'reference';
	const order: Type[] = ['user', 'feedback', 'project', 'reference'];

	function grouped(es: MemoryEntry[]): Record<Type, MemoryEntry[]> {
		return {
			user: es.filter((e) => e.type === 'user'),
			feedback: es.filter((e) => e.type === 'feedback'),
			project: es.filter((e) => e.type === 'project'),
			reference: es.filter((e) => e.type === 'reference')
		};
	}

	const groups = $derived(grouped(entries));

	const typeTone = {
		user: 'ember',
		feedback: 'moss',
		project: 'neutral',
		reference: 'outline'
	} as const;
</script>

<div class="flex flex-col gap-8 px-14 py-9 max-w-[1200px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>LIBRARY · MEMORY</Eyebrow>
		<Display size="lg">Memory</Display>
		<Heading size="sm" italic>
			What Forge has learned about you. User-editable; updates flow into every subsequent chat turn via the system prompt.
		</Heading>
	</div>

	{#if entries.length === 0}
		<Card surface="empty">
			<div class="flex flex-col gap-2 p-8 items-center">
				<Eyebrow>EMPTY</Eyebrow>
				<Body muted>
					Nothing saved yet. Memories accumulate as Forge learns from conversation — or add one manually below.
				</Body>
			</div>
		</Card>
	{/if}

	{#each order as t (t)}
		{@const bucket = groups[t]}
		{#if bucket.length > 0}
			<div class="flex flex-col gap-3">
				<div class="flex items-baseline gap-3 pb-2 border-b border-[var(--color-border)]">
					<Heading size="sm">{t}</Heading>
					<Chip tone={typeTone[t]}>{bucket.length}</Chip>
				</div>
				{#each bucket as e (e.filename)}
					<a href="/library/memory/{e.slug}">
						<Card surface="paper" class="transition-colors hover:border-[var(--color-stone)]">
							<div class="flex items-start justify-between gap-4 p-4">
								<div class="flex flex-col gap-1 min-w-0 flex-1">
									<span class="text-[15px] font-medium text-[var(--color-ink)]">
										{e.name}
									</span>
									<Body size="sm" muted>{e.description}</Body>
								</div>
								<div class="flex flex-col items-end gap-1 flex-shrink-0">
									<Meta size="xs">{e.filename}</Meta>
									{#if e.updated_at}<Meta size="xs">{e.updated_at}</Meta>{/if}
								</div>
							</div>
						</Card>
					</a>
				{/each}
			</div>
		{/if}
	{/each}
</div>
