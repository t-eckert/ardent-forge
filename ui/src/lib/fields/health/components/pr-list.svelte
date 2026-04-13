<script lang="ts">
	import { Card } from '$lib/components';
	import { Eyebrow, Stat } from '$lib/typography';

	interface Row {
		label: string;
		value: string;
	}

	interface Props {
		rows?: Row[];
	}

	let {
		rows = [
			{ label: '5K', value: '22:14' },
			{ label: '10K', value: '47:38' },
			{ label: 'Half', value: '1:48:22' },
			{ label: 'Back squat 5RM', value: '140 kg' },
			{ label: 'Bench 5RM', value: '95 kg' }
		]
	}: Props = $props();
</script>

<Card surface="paper">
	<div class="flex flex-col gap-3 p-[18px]">
		<Eyebrow>PERSONAL RECORDS</Eyebrow>
		<div class="flex flex-col gap-2.5 text-[13px]">
			{#each rows as row (row.label)}
				<div class="flex items-center justify-between">
					<span class="text-[var(--color-ink)]">{row.label}</span>
					<Stat value={row.value} size="sm" />
				</div>
			{/each}
		</div>
	</div>
</Card>
