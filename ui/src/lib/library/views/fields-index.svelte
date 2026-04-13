<script lang="ts">
	import type { Field } from '$lib/schemas/field';
	import FieldsGrid from '../components/fields-grid.svelte';
	import { Display, Heading, Eyebrow, Stat } from '$lib/typography';

	interface Props {
		fields: Field[];
		totalEntries?: number;
		totalWikiLinks?: number;
		lastEditTime?: string;
	}

	let {
		fields,
		totalEntries = 1412,
		totalWikiLinks = 3088,
		lastEditTime = '04:47'
	}: Props = $props();
</script>

<div class="flex flex-col gap-8 px-14 py-9 max-w-[1440px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>LIBRARY · FIELDS</Eyebrow>
		<div class="flex items-end justify-between gap-8">
			<Display size="lg">Fields</Display>
			<div class="flex gap-7">
				<div class="flex flex-col gap-1 items-start">
					<Eyebrow>ENTRIES</Eyebrow>
					<Stat value={totalEntries.toLocaleString()} size="lg" />
				</div>
				<div class="flex flex-col gap-1 items-start">
					<Eyebrow>WIKI LINKS</Eyebrow>
					<Stat value={totalWikiLinks.toLocaleString()} size="lg" />
				</div>
				<div class="flex flex-col gap-1 items-start">
					<Eyebrow>LAST EDIT</Eyebrow>
					<Stat value={lastEditTime} size="lg" />
				</div>
			</div>
		</div>
		<Heading size="sm" italic>
			Life areas, each with its own practice, people, and record.
		</Heading>
	</div>
	<FieldsGrid {fields} />
</div>
