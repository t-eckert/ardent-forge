<script lang="ts">
	import { Display, Eyebrow, Stat, Body, Meta } from '$lib/typography';
	import { Card } from '$lib/components';
	import type { Todo } from '$lib/schemas/todo';

	interface Props {
		/** Today's planned workout */
		workoutTitle: string;
		workoutSubtitle: string;
		pace: string;
		hr: string;
		fuel: string;
		todos: Todo[];
	}

	let { workoutTitle, workoutSubtitle, pace, hr, fuel, todos }: Props = $props();
</script>

<div class="flex gap-4">
	<Card surface="ember" class="flex-1">
		<div class="flex flex-col gap-3 p-[18px]">
			<span class="font-mono text-[10px] tracking-[0.12em] opacity-85">TODAY'S WORKOUT</span>
			<Display size="md" class="text-[var(--color-paper)]">{workoutTitle}</Display>
			<Body size="md" class="text-[var(--color-paper)] opacity-90">{workoutSubtitle}</Body>
			<div class="flex gap-6 pt-1.5">
				<div class="flex flex-col gap-0.5">
					<span class="font-mono text-[10px] tracking-wider opacity-75">PACE</span>
					<Stat value={pace} size="md" class="text-[var(--color-paper)]" />
				</div>
				<div class="flex flex-col gap-0.5">
					<span class="font-mono text-[10px] tracking-wider opacity-75">HR</span>
					<Stat value={hr} size="md" class="text-[var(--color-paper)]" />
				</div>
				<div class="flex flex-col gap-0.5">
					<span class="font-mono text-[10px] tracking-wider opacity-75">FUEL</span>
					<Stat value={fuel} size="md" class="text-[var(--color-paper)]" />
				</div>
			</div>
		</div>
	</Card>

	<Card surface="paper" class="flex-1">
		<div class="flex flex-col gap-2.5 p-[18px]">
			<div class="flex items-baseline justify-between">
				<Eyebrow>TODOS · DUE TODAY</Eyebrow>
				<Meta tone="ember">{todos.length} open</Meta>
			</div>
			<div class="flex flex-col gap-1.5">
				{#each todos as todo (todo.id)}
					<div class="flex items-center gap-2.5">
						<div
							class="w-3.5 h-3.5 rounded-[3px] flex-shrink-0"
							style={todo.status === 'review'
								? 'border: 1px solid var(--color-ember-deep); background: #FCE6DD;'
								: 'border: 1px solid var(--color-graphite);'}
						></div>
						<span class="flex-1 text-[13px] text-[var(--color-ink)] truncate">{todo.title}</span>
						<Meta size="xs" tone={todo.status === 'review' ? 'ember' : 'muted'}
							>{todo.category}</Meta
						>
					</div>
				{/each}
			</div>
		</div>
	</Card>
</div>
