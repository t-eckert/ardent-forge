<script lang="ts">
	import { Display, Body, Eyebrow, Stat } from '$lib/typography';
	import GoalStrip from '../components/goal-strip.svelte';
	import StatCard from '../components/stat-card.svelte';
	import WeeklyGrid from '../components/weekly-grid.svelte';
	import ActivityTable from '../components/activity-table.svelte';
	import SourcesCard from '../components/sources-card.svelte';
	import PrList from '../components/pr-list.svelte';
	import ReadinessCard from '../components/readiness-card.svelte';

	const weekDays = [
		{ dow: 'MON', date: '06', title: 'Upper · Push', source: 'NOTEBOOK', sourceTone: 'muted' as const, status: 'done' as const },
		{ dow: 'TUE', date: '07', title: 'Easy 8 km', source: 'STRAVA · 5:38 /km', sourceTone: 'ember' as const, status: 'done' as const },
		{ dow: 'WED', date: '08', title: 'Lower · Squat', source: 'NOTEBOOK', sourceTone: 'muted' as const, status: 'done' as const },
		{ dow: 'THU', date: '09', title: 'Tempo 6×1km', source: 'STRAVA · 4:48 /km', sourceTone: 'ember' as const, status: 'done' as const },
		{ dow: 'FRI', date: '10', title: 'Upper · Pull', source: 'NOTEBOOK', sourceTone: 'muted' as const, status: 'done' as const },
		{ dow: 'SAT · TODAY', date: '11', title: 'Long run 18 km', source: 'PLAN · 5:20 /km', sourceTone: 'muted' as const, status: 'today' as const, highlight: true },
		{ dow: 'SUN', date: '12', title: 'Mobility · 30 m', source: 'NOTEBOOK', sourceTone: 'muted' as const, status: 'open' as const }
	];

	const activityRows = [
		{ date: 'Apr 10', title: 'Tempo 6×1km', type: 'run', volume: '10.2 km · 48:21', intensity: '172 bpm · Z4', source: 'strava' as const },
		{ date: 'Apr 10', title: 'Upper · Pull · A', type: 'strength', volume: '18 sets · 52 min', intensity: 'RPE 7', source: 'notebook' as const },
		{ date: 'Apr 09', title: 'Easy 8 km · Canal loop', type: 'run', volume: '8.1 km · 45:30', intensity: '148 bpm · Z2', source: 'strava' as const },
		{ date: 'Apr 08', title: 'Lower · Squat · B', type: 'strength', volume: '14 sets · 58 min', intensity: 'RPE 8 · back squat 125 kg', source: 'notebook' as const },
		{ date: 'Apr 07', title: 'Easy 8 km', type: 'run', volume: '8.0 km · 45:04', intensity: '146 bpm · Z2', source: 'strava' as const },
		{ date: 'Apr 06', title: 'Upper · Push · A', type: 'strength', volume: '16 sets · 54 min', intensity: 'RPE 7 · bench 90 kg', source: 'notebook' as const },
		{ date: 'Apr 05', title: 'Long run · Gatineau', type: 'run', volume: '17.5 km · 1:35:12', intensity: '152 bpm · Z2', source: 'strava' as const }
	];
</script>

<div class="flex flex-col gap-7 px-14 py-9 max-w-[1440px] mx-auto">
	<!-- Title block -->
	<div class="flex flex-col gap-1.5">
		<Eyebrow>FIELD · HEALTH · WORKOUTS</Eyebrow>
		<div class="flex items-end justify-between gap-8">
			<Display size="xl">Workouts</Display>
			<div class="flex gap-9">
				<div class="flex flex-col gap-1 items-start">
					<Eyebrow>THIS WEEK</Eyebrow>
					<Stat value={6} size="lg" />
				</div>
				<div class="flex flex-col gap-1 items-start">
					<Eyebrow>THIS BLOCK</Eyebrow>
					<Stat value={28} size="lg" />
				</div>
				<div class="flex flex-col gap-1 items-start">
					<Eyebrow>YTD KM</Eyebrow>
					<Stat value={412} size="lg" />
				</div>
			</div>
		</div>
		<Body size="lg" class="font-display italic text-[var(--color-slate)]">
			Run, lift, recover. The practice of keeping the body game-ready.
		</Body>
	</div>

	<!-- Goal strip -->
	<GoalStrip
		goal="Sub-1:45 half marathon"
		event="Ottawa Race Weekend · 24 May 2026"
		daysToRace={42}
		blockLabel="week 8 of 14 · taper in 4 wk"
		goalPace="4:58"
		thresholdNote="current threshold · 5:08 /km"
	/>

	<!-- Stat cards -->
	<div class="grid grid-cols-4 gap-4">
		<StatCard label="WEEKLY VOLUME" value={46} unit="km" delta="+8%" deltaTone="moss" />
		<StatCard label="LONG RUN" value={18.5} unit="km" delta="peak: 21.1" deltaTone="muted" />
		<StatCard label="ZONE 2 TIME" value="3:48" unit="hr" />
		<StatCard label="STRENGTH" value={2} unit="/wk" />
	</div>

	<!-- Lower two-column -->
	<div class="flex gap-8">
		<div class="flex flex-col flex-1 gap-9 min-w-0">
			<WeeklyGrid days={weekDays} />
			<ActivityTable rows={activityRows} />
		</div>
		<div class="flex flex-col w-[320px] gap-5 flex-shrink-0">
			<SourcesCard />
			<PrList />
			<ReadinessCard />
		</div>
	</div>
</div>
