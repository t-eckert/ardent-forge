import { z } from 'zod';

/**
 * code.diff — the tool result emitted when the AI proposes a code change.
 *
 * The widget renders file list + first hunk preview + footer actions. Actions are
 * expressed as typed variants so the frontend can route them through the right
 * handler (view diff vs. open PR vs. request changes).
 */

export const DiffLine = z.object({
	kind: z.enum(['context', 'add', 'remove']),
	/** Line number in the new file for `add` / `context`, old file for `remove` */
	line: z.number().int().nonnegative(),
	content: z.string()
});

export const DiffHunk = z.object({
	/** Header summary (first N lines of actual change for the preview) */
	lines: z.array(DiffLine).max(20)
});

export const DiffFile = z.object({
	path: z.string(),
	changes: z.number().int().nonnegative(),
	additions: z.number().int().nonnegative(),
	deletions: z.number().int().nonnegative(),
	/** Optional preview — only the first file typically carries one */
	hunk: DiffHunk.optional()
});

export const CodeDiffAction = z.discriminatedUnion('kind', [
	z.object({ kind: z.literal('view-diff'), label: z.string() }),
	z.object({ kind: z.literal('commit'), label: z.string() }),
	z.object({ kind: z.literal('open-pr'), label: z.string() }),
	z.object({ kind: z.literal('request-changes'), label: z.string() }),
	z.object({ kind: z.literal('approve-merge'), label: z.string() })
]);

export const CodeDiffPayload = z.object({
	tool: z.literal('code.diff'),
	/** Repo / workspace context — rendered in the header */
	context: z.string(),
	branch: z.string(),
	/** Aggregate stats for the whole diff */
	additions: z.number().int().nonnegative(),
	deletions: z.number().int().nonnegative(),
	files: z.array(DiffFile).min(1),
	/** Metadata shown top-right of footer */
	footerMeta: z.string().optional(),
	actions: z.array(CodeDiffAction).min(1)
});

export type DiffLine = z.infer<typeof DiffLine>;
export type DiffHunk = z.infer<typeof DiffHunk>;
export type DiffFile = z.infer<typeof DiffFile>;
export type CodeDiffAction = z.infer<typeof CodeDiffAction>;
export type CodeDiffPayload = z.infer<typeof CodeDiffPayload>;
