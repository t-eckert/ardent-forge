import type { ResultPayload } from '$lib/schemas/widgets';

export function makeResearchResult(): ResultPayload {
	return {
		tool: 'result',
		label: 'research output',
		data: {
			status: 'ok',
			files: ['Wiki/Svelte 5 Breaking Changes.md'],
			new_files: ['Wiki/Svelte 5 Breaking Changes.md'],
			notebook_commit_pending: true,
			source_url: 'https://svelte.dev/docs/svelte/v5-migration-guide',
			claude_output:
				'Collected the Svelte 5 migration guide and cross-referenced with the ' +
				'official changelog. Primary surface-level changes: runes replace reactive ' +
				'declarations ($state, $derived, $effect), event handlers switch from ' +
				'on:click to onclick, slot usage is replaced by snippets (#snippet / @render), ' +
				'and export let is superseded by $props(). Several stores behaviours also ' +
				'changed — notably setting a store no longer triggers $: reactivity outside ' +
				'of a component. Notes file ready for commit to Notebook.'
		}
	};
}

export function makeCodeResult(): ResultPayload {
	return {
		tool: 'result',
		label: 'code output',
		data: {
			pr_url: 'https://github.com/t-eckert/ardent-forge/pull/42',
			files_changed: 6,
			lines_added: 142,
			lines_removed: 17,
			branch: 'feat/rename-tclient'
		}
	};
}
