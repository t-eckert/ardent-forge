<script lang="ts">
	import type { WidgetPayload } from '$lib/schemas/widgets';
	import CodeDiff from '../code-diff/code-diff.svelte';

	/**
	 * Renders any tool payload by discriminating on `tool`. Widget-host is the single
	 * entry point the chat renderer and agent-run artifact both use — add a new case here
	 * whenever a new widget ships.
	 *
	 * The `payload` prop is a discriminated union; the compiler enforces exhaustiveness
	 * (remove a case and TS complains about the uncovered branch).
	 */

	interface Props {
		payload: WidgetPayload;
	}

	let { payload }: Props = $props();
</script>

{#if payload.tool === 'code.diff'}
	<CodeDiff {payload} />
{:else}
	<!-- unreachable once every tool in the discriminator has a render branch -->
	<div class="font-mono text-[11px] text-[var(--color-warn)]">
		unknown tool: {(payload as { tool: string }).tool}
	</div>
{/if}
