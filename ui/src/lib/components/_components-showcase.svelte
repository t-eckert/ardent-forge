<script lang="ts">
	import Button from './button.svelte';
	import Chip from './chip.svelte';
	import KeycapHint from './keycap-hint.svelte';
	import StatusDot from './status-dot.svelte';
	import Divider from './divider.svelte';
	import Card from './card.svelte';
	import EmptyState from './empty-state.svelte';
	import Spinner from './spinner.svelte';
	import Avatar from './avatar.svelte';
	import PinMarker from './pin-marker.svelte';
	import { Eyebrow, Body, Stat, Heading } from '$lib/typography';
</script>

<div class="p-12 max-w-4xl flex flex-col gap-10">
	<div class="flex flex-col gap-3">
		<Eyebrow>BUTTON</Eyebrow>
		<div class="flex gap-3 items-center">
			<Button variant="primary">Apply &amp; open PR</Button>
			<Button variant="secondary">View diff</Button>
			<Button variant="ghost">Cancel</Button>
			<Button variant="danger">Abort run</Button>
		</div>
		<div class="flex gap-3 items-center">
			<Button variant="secondary" size="sm">sm</Button>
			<Button variant="secondary" size="md">md</Button>
			<Button variant="secondary" size="lg">lg</Button>
		</div>
	</div>

	<div class="flex flex-col gap-3">
		<Eyebrow>CHIP</Eyebrow>
		<div class="flex gap-3 items-center">
			<Chip tone="neutral">notebook</Chip>
			<Chip tone="ember">strava</Chip>
			<Chip tone="moss">● done</Chip>
			<Chip tone="ink">all</Chip>
			<Chip tone="outline">delivery</Chip>
		</div>
	</div>

	<div class="flex flex-col gap-3">
		<Eyebrow>KEYCAP HINT</Eyebrow>
		<div class="flex gap-4 items-center">
			<KeycapHint keys={['⌘', 'K']} />
			<KeycapHint keys={['⌘', '↵']} />
			<KeycapHint keys={['esc']} />
			<KeycapHint keys={['↑']} />
			<KeycapHint keys={['↓']} />
		</div>
	</div>

	<div class="flex flex-col gap-3">
		<Eyebrow>STATUS DOT</Eyebrow>
		<div class="flex gap-3 items-center">
			<StatusDot tone="moss" /><Body size="sm" muted>live</Body>
			<StatusDot tone="ember" /><Body size="sm" muted>active</Body>
			<StatusDot tone="warn" /><Body size="sm" muted>blocked</Body>
			<StatusDot tone="signal" /><Body size="sm" muted>info</Body>
			<StatusDot tone="graphite" /><Body size="sm" muted>inactive</Body>
		</div>
	</div>

	<div class="flex flex-col gap-3">
		<Eyebrow>CARD</Eyebrow>
		<div class="flex gap-3">
			<Card surface="paper">
				<div class="p-4 flex flex-col gap-2 w-56">
					<Eyebrow>PAPER</Eyebrow>
					<Stat value="46" unit="km" size="xl" />
				</div>
			</Card>
			<Card surface="bench">
				<div class="p-4 flex flex-col gap-2 w-56">
					<Eyebrow>BENCH</Eyebrow>
					<Stat value="18.5" unit="km" size="xl" />
				</div>
			</Card>
			<Card surface="ember">
				<div class="p-4 flex flex-col gap-2 w-56">
					<Eyebrow>EMBER · HERO</Eyebrow>
					<Stat value="4:58" unit="/km" size="xl" tone="default" class="text-[var(--color-paper)]" />
				</div>
			</Card>
			<Card surface="empty">
				<div class="p-4 flex items-center justify-center w-56 h-24">
					<Body size="sm" muted>+ Add field</Body>
				</div>
			</Card>
		</div>
	</div>

	<div class="flex flex-col gap-3">
		<Eyebrow>AVATAR</Eyebrow>
		<div class="flex gap-3 items-center">
			<Avatar label="S" tone="ember" />
			<Avatar label="N" tone="signal" />
			<Avatar label="G" tone="graphite" />
			<Avatar label={'{ }'} tone="ink" />
			<Avatar label="♥" tone="ember" size="lg" />
		</div>
	</div>

	<div class="flex flex-col gap-3">
		<Eyebrow>PIN MARKER</Eyebrow>
		<div class="flex gap-4 items-center">
			<PinMarker label="1" active />
			<PinMarker label="2" />
			<PinMarker label="3" />
			<PinMarker label="4" />
		</div>
	</div>

	<div class="flex flex-col gap-3">
		<Eyebrow>DIVIDER</Eyebrow>
		<div class="flex flex-col gap-2">
			<Heading size="md">Section A</Heading>
			<Divider />
			<Heading size="md">Section B</Heading>
		</div>
	</div>

	<div class="flex flex-col gap-3">
		<Eyebrow>SPINNER + EMPTY STATE</Eyebrow>
		<div class="flex gap-8 items-center">
			<div class="flex items-center gap-2">
				<Spinner size="sm" />
				<Spinner size="md" />
				<Spinner size="lg" />
			</div>
			<Card surface="paper">
				<EmptyState title="No runs yet" message="TRIGGERED RUNS WILL APPEAR HERE" />
			</Card>
		</div>
	</div>
</div>
