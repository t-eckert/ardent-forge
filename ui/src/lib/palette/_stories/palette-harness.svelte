<script lang="ts">
	import PaletteOverlay from '../components/palette-overlay.svelte';
	import { palette } from '../state/palette.state.svelte';
	import { MOCK_RESULTS } from './mock-data';
	import { Button } from '$lib/components';
	import { Display, Body } from '$lib/typography';

	interface Props {
		/** Auto-open the palette on mount for storybook visual */
		openOnMount?: boolean;
	}

	let { openOnMount = true }: Props = $props();

	$effect(() => {
		if (openOnMount) palette.show();
	});
</script>

<div class="min-h-screen bg-[var(--color-paper)] p-12">
	<div class="max-w-2xl flex flex-col gap-4">
		<Display size="lg">Palette harness</Display>
		<Body muted>
			The palette is rendered as a full-viewport overlay. Press ⌘K, or click the button below to
			open manually.
		</Body>
		<div>
			<Button variant="primary" onclick={() => palette.show()}>Open ⌘K</Button>
		</div>
	</div>

	<PaletteOverlay results={MOCK_RESULTS} />
</div>
