<script lang="ts">
	import DOMPurify from 'dompurify';
	import { marked } from 'marked';
	import { api } from '$lib/api/typed';

	interface Props {
		source: string;
		/** Vault-relative path (e.g. "Log/2026-06-12.md"). When provided,
		 *  checkboxes become interactive and write back to the notebook. */
		path?: string;
		class?: string;
	}

	let { source, path, class: klass = '' }: Props = $props();

	// Local copy so optimistic checkbox updates can re-render without
	// the parent needing to refetch the whole file.
	let localSource = $state(source);
	$effect(() => {
		localSource = source;
	});

	// ── Frontmatter ──────────────────────────────────────────────────────────
	// Strip YAML frontmatter for display but track how many lines it occupies
	// so data-line attributes map to the correct file line numbers.
	const fmMatch = $derived(localSource.match(/^---\n[\s\S]*?\n---\n?/));
	const fmOffset = $derived(fmMatch ? (fmMatch[0].match(/\n/g) ?? []).length : 0);
	const displaySource = $derived(fmMatch ? localSource.slice(fmMatch[0].length) : localSource);

	// ── Checkbox pre-processing ───────────────────────────────────────────────
	// Replace `- [marker] ` with a span that carries the file line number and
	// current marker as data attributes. This runs before marked so the
	// rendered HTML has our custom elements instead of disabled <input>s.
	const processedSource = $derived(
		displaySource
			.split('\n')
			.map((line, idx) =>
				line.replace(
					/^(\s*- )\[([x\->!~ ])\]( )/,
					(_, pre, mk, post) =>
						`${pre}<span class="nc-cb" data-line="${idx + fmOffset}" data-mk="${mk}"></span>${post}`
				)
			)
			.join('\n')
	);

	// ── Rendering ─────────────────────────────────────────────────────────────
	function escapeHtml(s: string): string {
		return s
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/"/g, '&quot;');
	}

	function convertWikilinks(text: string): string {
		return text.replace(/\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]/g, (_match, target, display) => {
			const label = escapeHtml(display || target);
			const href = `/library/wiki/${encodeURIComponent(target)}`;
			return `<a href="${href}" class="wikilink">${label}</a>`;
		});
	}

	const html = $derived(
		DOMPurify.sanitize(
			marked.parse(convertWikilinks(processedSource), { async: false }) as string,
			{ ADD_ATTR: ['data-line', 'data-mk'] }
		)
	);

	// ── Context menu ──────────────────────────────────────────────────────────
	type MenuState = { x: number; y: number; line: number; marker: string };
	let menu = $state<MenuState | null>(null);

	const STATES = [
		{ marker: 'x', label: 'Completed' },
		{ marker: '>', label: 'Rescheduled' },
		{ marker: '-', label: 'Deferred' },
		{ marker: '!', label: 'Not completed' },
		{ marker: '~', label: 'In progress' },
		{ marker: ' ', label: 'Clear' }
	] as const;

	// ── Interactions ──────────────────────────────────────────────────────────
	async function applyMarker(line: number, marker: string) {
		menu = null;
		if (!path) return;

		// Optimistic update — rewrite the marker on that line immediately
		const lines = localSource.split('\n');
		lines[line] = lines[line].replace(/\[([x\->!~ ])\]/, `[${marker}]`);
		localSource = lines.join('\n');

		try {
			await api.notebook.updateCheckbox(path, line, marker);
		} catch {
			localSource = source; // revert on failure
		}
	}

	function handleClick(e: MouseEvent) {
		if (!path) return;
		const cb = (e.target as Element).closest<HTMLElement>('.nc-cb');
		if (!cb) return;
		e.preventDefault();
		const line = parseInt(cb.dataset.line!);
		const mk = cb.dataset.mk!;
		// Completed → clear; anything else → complete
		applyMarker(line, mk === 'x' ? ' ' : 'x');
	}

	function handleContextMenu(e: MouseEvent) {
		if (!path) return;
		const cb = (e.target as Element).closest<HTMLElement>('.nc-cb');
		if (!cb) return;
		e.preventDefault();
		menu = {
			x: e.clientX,
			y: e.clientY,
			line: parseInt(cb.dataset.line!),
			marker: cb.dataset.mk!
		};
	}
</script>

<!-- Context menu backdrop + popup -->
{#if menu}
	<div class="fixed inset-0 z-40" onclick={() => (menu = null)} role="presentation"></div>
	<div
		class="fixed z-50 bg-[var(--color-paper)] border border-[var(--color-border)] rounded-lg shadow-xl py-1 min-w-[172px]"
		style="left: {menu.x}px; top: {menu.y}px;"
	>
		{#each STATES as state}
			{#if state.marker !== menu.marker}
				<button
					class="w-full flex items-center gap-2.5 px-3 py-1.5 text-left text-[13px] text-[var(--color-ink)] hover:bg-[var(--color-bench)] transition-colors"
					onclick={() => applyMarker(menu!.line, state.marker)}
				>
					<span class="nc-preview" data-mk={state.marker}></span>
					{state.label}
				</button>
			{/if}
		{/each}
	</div>
{/if}

<div
	class="notebook-prose {klass}"
	role="presentation"
	onclick={handleClick}
	oncontextmenu={handleContextMenu}
>
	{@html html}
</div>

<style>
	/* ── Checkbox spans (injected via {@html}, need :global) ────────────────── */
	:global(.nc-cb) {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 15px;
		height: 15px;
		border-radius: 3px;
		border: 1.5px solid var(--color-stone);
		cursor: pointer;
		vertical-align: middle;
		flex-shrink: 0;
		position: relative;
		box-sizing: border-box;
		transition:
			border-color 0.1s,
			background-color 0.1s,
			opacity 0.1s;
		margin-right: 0.25em;
		user-select: none;
	}
	:global(.nc-cb:hover) {
		opacity: 0.7;
	}

	/* Preview spans in the context menu live in Svelte template scope */
	.nc-preview {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 13px;
		height: 13px;
		border-radius: 2px;
		border: 1.5px solid var(--color-stone);
		flex-shrink: 0;
		position: relative;
		box-sizing: border-box;
	}

	/* ── Completed [x] ── */
	:global(.nc-cb[data-mk='x']),
	.nc-preview[data-mk='x'] {
		background: var(--color-moss);
		border-color: var(--color-moss);
	}
	:global(.nc-cb[data-mk='x'])::after,
	.nc-preview[data-mk='x']::after {
		content: '';
		display: block;
		width: 4px;
		height: 7px;
		border: 1.5px solid white;
		border-top: none;
		border-left: none;
		transform: rotate(45deg) translate(-1px, -1px);
	}

	/* ── Deferred [-] ── */
	:global(.nc-cb[data-mk='-']),
	.nc-preview[data-mk='-'] {
		border-color: var(--color-graphite);
	}
	:global(.nc-cb[data-mk='-'])::after,
	.nc-preview[data-mk='-']::after {
		content: '';
		width: 7px;
		height: 1.5px;
		background: var(--color-graphite);
	}

	/* ── Rescheduled [>] ── */
	:global(.nc-cb[data-mk='>']),
	.nc-preview[data-mk='>'] {
		border-color: #5b8dd9;
	}
	:global(.nc-cb[data-mk='>'])::after,
	.nc-preview[data-mk='>']::after {
		content: '›';
		font-size: 14px;
		line-height: 1;
		color: #5b8dd9;
		margin-top: -1px;
	}

	/* ── Not completed [!] ── */
	:global(.nc-cb[data-mk='!']),
	.nc-preview[data-mk='!'] {
		border-color: var(--color-ember);
	}
	:global(.nc-cb[data-mk='!'])::after,
	.nc-preview[data-mk='!']::after {
		content: '×';
		font-size: 12px;
		line-height: 1;
		color: var(--color-ember);
	}

	/* ── In progress [~] ── */
	:global(.nc-cb[data-mk='~']),
	.nc-preview[data-mk='~'] {
		border-color: var(--color-slate);
	}
	:global(.nc-cb[data-mk='~'])::after,
	.nc-preview[data-mk='~']::after {
		content: '~';
		font-size: 11px;
		line-height: 1;
		color: var(--color-slate);
	}

	/* ── Prose styles ─────────────────────────────────────────────────────────── */
	.notebook-prose :global(h1) {
		font-family: var(--font-display);
		font-size: 1.75rem;
		font-weight: 500;
		margin-top: 1.5rem;
		margin-bottom: 0.75rem;
		color: var(--color-ink);
	}
	.notebook-prose :global(h2) {
		font-family: var(--font-display);
		font-size: 1.35rem;
		font-weight: 500;
		margin-top: 1.25rem;
		margin-bottom: 0.5rem;
		color: var(--color-ink);
	}
	.notebook-prose :global(h3) {
		font-size: 1.1rem;
		font-weight: 600;
		margin-top: 1rem;
		margin-bottom: 0.4rem;
		color: var(--color-ink);
	}
	.notebook-prose :global(p) {
		font-size: 0.9375rem;
		line-height: 1.65;
		color: var(--color-ink);
		margin-bottom: 0.6rem;
	}
	.notebook-prose :global(ul) {
		padding-left: 1.5rem;
		margin-bottom: 0.6rem;
		list-style-type: disc;
	}
	.notebook-prose :global(ol) {
		padding-left: 1.5rem;
		margin-bottom: 0.6rem;
		list-style-type: decimal;
	}
	.notebook-prose :global(li) {
		font-size: 0.9375rem;
		line-height: 1.65;
		color: var(--color-ink);
	}
	/* Task list items get no bullet since the checkbox span replaces it */
	.notebook-prose :global(li:has(.nc-cb)) {
		list-style: none;
		margin-left: -1.5rem;
	}
	.notebook-prose :global(blockquote) {
		border-left: 3px solid var(--color-ember);
		padding-left: 1rem;
		margin: 0.75rem 0;
		color: var(--color-slate);
		font-style: italic;
	}
	.notebook-prose :global(code) {
		font-family: var(--font-mono);
		font-size: 0.85em;
		background: var(--color-bench);
		padding: 0.15em 0.35em;
		border-radius: 3px;
	}
	.notebook-prose :global(pre) {
		background: var(--color-bench);
		padding: 1rem;
		border-radius: 6px;
		overflow-x: auto;
		margin-bottom: 0.75rem;
	}
	.notebook-prose :global(pre code) {
		background: none;
		padding: 0;
	}
	.notebook-prose :global(a) {
		color: var(--color-ember-deep);
		text-decoration: none;
	}
	.notebook-prose :global(a:hover) {
		text-decoration: underline;
	}
	.notebook-prose :global(hr) {
		border: none;
		border-top: 1px solid var(--color-border);
		margin: 1.5rem 0;
	}
	.notebook-prose :global(table) {
		width: 100%;
		border-collapse: collapse;
		margin-bottom: 0.75rem;
		font-size: 0.875rem;
	}
	.notebook-prose :global(th),
	.notebook-prose :global(td) {
		border: 1px solid var(--color-border);
		padding: 0.4rem 0.6rem;
		text-align: left;
	}
	.notebook-prose :global(th) {
		background: var(--color-bench);
		font-weight: 600;
	}
</style>
