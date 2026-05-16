<script lang="ts">
	import HeroGreeting from '../components/hero-greeting.svelte';
	import TodayShape from '../components/today-shape.svelte';
	import FocusBlock from '../components/focus-block.svelte';
	import Composer from '../components/composer.svelte';
	import OvernightDigest from '../components/overnight-digest.svelte';
	import OpenThreads from '../components/open-threads.svelte';
	import YesterdaySummary from '../components/yesterday-summary.svelte';
	import type { Thread } from '$lib/schemas/thread';
	import type { AgentRun } from '$lib/schemas/agent';
	import type { Todo } from '$lib/schemas/todo';
	import type { WeatherCurrent } from '$lib/api/typed';

	interface YesterdayRow {
		label: string;
		value: string;
	}

	interface Props {
		threads?: Thread[];
		weather?: WeatherCurrent | null;
		runs?: AgentRun[];
		todos?: Todo[];
		yesterdayRows?: YesterdayRow[];
	}

	let {
		threads: threadsProp = [],
		weather = null,
		runs: runsProp = [],
		todos: todosProp = [],
		yesterdayRows: yesterdayRowsProp = []
	}: Props = $props();

	const threads = $derived(threadsProp ?? []);
	const runs = $derived(runsProp ?? []);
	const todos = $derived(todosProp ?? []);

	// Schedule — will be wired when a Calendar connector ships.
	const scheduleItems: { time: string; title: string; note: string; tag?: { label: string; tone?: 'ember' | 'neutral' | 'moss' }; highlight?: boolean }[] = [];

	// Derive hero notes from real data.
	const todosDueNote = $derived(() => {
		const blocked = todos.filter((t) => t.status === 'blocked').length;
		const review = todos.filter((t) => t.status === 'review').length;
		const parts: string[] = [];
		if (blocked) parts.push(`${blocked} blocked`);
		if (review) parts.push(`${review} review`);
		return parts.join(' · ') || undefined;
	});

	const needsReview = $derived(runs.filter((r) => r.status === 'needs-review').length);
	const agentsNote = $derived(
		needsReview > 0 ? `${needsReview} need${needsReview === 1 ? 's' : ''} review` : 'all clear'
	);

	const subtitle = $derived(() => {
		const parts: string[] = [];

		// Agent overnight summary
		if (runs.length > 0) {
			const s = runs.length === 1 ? '' : 's';
			if (needsReview > 0) {
				parts.push(`${runs.length} agent run${s} overnight — ${needsReview} need${needsReview === 1 ? 's' : ''} your review`);
			} else {
				parts.push(`${runs.length} agent run${s} finished overnight, all clear`);
			}
		}

		// Todos summary
		const pendingTodos = todos.filter((t) => t.status !== 'done').length;
		if (pendingTodos > 0) {
			const s = pendingTodos === 1 ? '' : 's';
			parts.push(`${pendingTodos} todo${s} on your plate`);
		}

		// Weather note
		if (weather) {
			parts.push(`${Math.round(weather.currentC)}°C and ${weather.summary.toLowerCase()} outside`);
		}

		if (parts.length === 0) return 'A quiet day ahead.';

		// Join with " — " for the first break, then ", " for the rest
		// Capitalize the first letter
		const sentence = parts.join(' — ');
		return sentence.charAt(0).toUpperCase() + sentence.slice(1) + '.';
	});
</script>

<div class="flex flex-col gap-7 px-14 pt-9 pb-6 max-w-[1440px] mx-auto">
	<HeroGreeting
		subtitle={subtitle()}
		weatherTempC={weather?.currentC ?? 0}
		weatherSummary={weather?.summary ?? '—'}
		todosDue={todos.filter((t) => t.status !== 'done').length}
		todosDueNote={todosDueNote()}
		agentsOvernight={runs.length}
		{agentsNote}
	/>

	<div class="flex gap-9">
		<div class="flex flex-col flex-1 gap-8 min-w-0">
			{#if scheduleItems.length > 0}
				<TodayShape items={scheduleItems} />
			{/if}
			<FocusBlock
				workoutTitle="—"
				workoutSubtitle="No workout connector configured."
				pace="—"
				hr="—"
				fuel="—"
				{todos}
			/>
			<Composer />
		</div>

		<div class="flex flex-col w-[400px] gap-7 flex-shrink-0">
			<OvernightDigest {runs} />
			<OpenThreads {threads} />
			<YesterdaySummary rows={yesterdayRowsProp} />
		</div>
	</div>
</div>
