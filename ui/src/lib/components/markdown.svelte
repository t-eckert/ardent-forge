<script lang="ts">
	import { marked } from 'marked';

	interface Props {
		source: string;
		class?: string;
	}

	let { source, class: klass = '' }: Props = $props();

	// Convert Obsidian wikilinks [[Name]] and [[Name|Display]] to HTML links.
	function convertWikilinks(text: string): string {
		return text.replace(/\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]/g, (_match, target, display) => {
			const label = display || target;
			const href = `/library/wiki/${encodeURIComponent(target)}`;
			return `<a href="${href}" class="wikilink">${label}</a>`;
		});
	}

	const html = $derived(marked.parse(convertWikilinks(source), { async: false }) as string);
</script>

<div class="notebook-prose {klass}">
	{@html html}
</div>

<style>
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
	.notebook-prose :global(ul),
	.notebook-prose :global(ol) {
		padding-left: 1.5rem;
		margin-bottom: 0.6rem;
	}
	.notebook-prose :global(li) {
		font-size: 0.9375rem;
		line-height: 1.65;
		color: var(--color-ink);
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
