<script lang="ts">
	import HeroGreeting from '../components/hero-greeting.svelte';
	import TodayShape from '../components/today-shape.svelte';
	import FocusBlock from '../components/focus-block.svelte';
	import Composer from '../components/composer.svelte';
	import OvernightDigest from '../components/overnight-digest.svelte';
	import OpenThreads from '../components/open-threads.svelte';
	import YesterdaySummary from '../components/yesterday-summary.svelte';
	import type { Thread } from '$lib/schemas/thread';
	import { makeTodaysTodos, makeOvernightRuns, makeThreadList } from '$lib/mocks';

	interface Props {
		threads?: Thread[];
	}

	let { threads: threadsProp }: Props = $props();

	const todos = makeTodaysTodos();
	const runs = makeOvernightRuns();
	// Overnight-run and todos endpoints don't exist yet — mocks stay until they do.
	const threads = $derived(threadsProp ?? makeThreadList());

	const scheduleItems = [
		{
			time: '08:00',
			title: 'Morning walk with Winona',
			note: 'PERSONAL · 30 min'
		},
		{
			time: '10:00',
			title: 'Long run · 18 km · Canal → Gatineau',
			note: 'PLAN · 5:20 /km · ~1:36',
			tag: { label: 'training', tone: 'ember' as const },
			highlight: true
		},
		{
			time: '14:00',
			title: 'Painting session · Chaos submission',
			note: 'ART · watercolour · 2h'
		},
		{
			time: '17:30',
			title: 'Tomorrow prep · notebook log',
			note: 'RITUAL · 15 min'
		}
	];
</script>

<div class="flex flex-col gap-7 px-14 pt-9 pb-6 max-w-[1440px] mx-auto">
	<HeroGreeting
		weatherTempC={6}
		weatherSummary="clear → sunny ↑14°"
		todosDue={todos.length}
		todosDueNote="2 blocked · 1 review"
		agentsOvernight={runs.length}
		agentsNote="overnight · 1 needs you"
	/>

	<div class="flex gap-9">
		<div class="flex flex-col flex-1 gap-8 min-w-0">
			<TodayShape items={scheduleItems} />
			<FocusBlock
				workoutTitle="Long run · 18 km"
				workoutSubtitle="Build block, wk 08. Stay Z2 for first 14, float to threshold last 4."
				pace="5:20 /km"
				hr="145–158"
				fuel="1 gel @ 10k"
				{todos}
			/>
			<Composer />
		</div>

		<div class="flex flex-col w-[400px] gap-7 flex-shrink-0">
			<OvernightDigest {runs} />
			<OpenThreads {threads} />
			<YesterdaySummary />
		</div>
	</div>
</div>
