<script lang="ts">
	import Display from './display.svelte';
	import Heading from './heading.svelte';
	import Body from './body.svelte';
	import Meta from './meta.svelte';
	import Stat from './stat.svelte';
	import Eyebrow from './eyebrow.svelte';
</script>

<div class="p-12 max-w-3xl flex flex-col gap-10">
	<div class="flex flex-col gap-2">
		<Eyebrow>TYPOGRAPHY · V0.1</Eyebrow>
		<Display size="xl">Run the forge.</Display>
		<Heading size="lg" italic>Headlines, section titles, hero moments.</Heading>
	</div>

	<div class="flex flex-col gap-3">
		<Eyebrow>DISPLAY</Eyebrow>
		<Display size="xl">Workouts</Display>
		<Display size="lg">Good morning, Thomas.</Display>
		<Display size="md">Morning briefing</Display>
	</div>

	<div class="flex flex-col gap-3">
		<Eyebrow>HEADING</Eyebrow>
		<Heading size="lg">Code changes</Heading>
		<Heading size="md">Today's shape</Heading>
		<Heading size="sm" italic>Recent sessions</Heading>
	</div>

	<div class="flex flex-col gap-2">
		<Eyebrow>BODY</Eyebrow>
		<Body size="lg">
			Ardent Forge coordinates tasks across repositories and surfaces their state where
			you'll actually see it. Agents do the reach; you do the judgment.
		</Body>
		<Body>14px default — table rows, metadata, paragraph text.</Body>
		<Body size="sm" muted>12px muted for secondary descriptions and dense meta rows.</Body>
	</div>

	<div class="flex flex-col gap-2">
		<Eyebrow>META · MONO LABELS</Eyebrow>
		<Meta>FORGE · CODE+TOOLS · 14:06</Meta>
		<Meta tone="ember">STRAVA · 5:38 /km</Meta>
		<Meta tone="moss">● live</Meta>
	</div>

	<div class="flex flex-col gap-3">
		<Eyebrow>STAT · NUMBERS ALWAYS MONO</Eyebrow>
		<div class="flex gap-6 items-baseline">
			<Stat value="46" unit="km" size="xl" />
			<Stat value="18.5" unit="km" size="xl" />
			<Stat value="3:48" unit="hr" size="xl" />
			<Stat value="82" unit="/100" size="xl" />
		</div>
		<div class="flex gap-6 items-baseline">
			<Stat value="4:58" unit="/km" size="2xl" />
			<Stat value="42" size="2xl" />
		</div>
	</div>
</div>
