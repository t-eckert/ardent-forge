import { z } from 'zod';

/**
 * code.result — the artifact a completed code-agent task emits.
 *
 * Distinct from code.diff (which embeds actual hunks). This is the
 * summary card shown in a thread's task-resolved message: where the
 * PR landed, what branch was pushed, and optionally a short prose
 * summary from the agent's Claude run.
 */
export const CodeResultPayload = z.object({
	tool: z.literal('code.result'),
	prUrl: z.string().optional(),
	branch: z.string().optional(),
	summary: z.string().optional(),
	/** Trimmed transcript of what Claude Code produced while running. */
	claudeOutput: z.string().optional()
});

export type CodeResultPayload = z.infer<typeof CodeResultPayload>;
