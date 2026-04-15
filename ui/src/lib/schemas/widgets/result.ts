import { z } from 'zod';

/**
 * result — generic escape-hatch widget for arbitrary agent output.
 *
 * Rendered when a resolved task's `result` dict doesn't match any specific
 * widget shape (code.diff, places.map, etc.). Lists every key→value pair
 * in a mono grid with light special handling for URLs and arrays.
 *
 * Per-agent widget shapes should be added as their own discriminated
 * variants — this exists so agent output never goes unrendered while
 * those richer shapes are being specced.
 */
export const ResultPayload = z.object({
	tool: z.literal('result'),
	/** Header label — typically "${task.type} output" */
	label: z.string(),
	/** Raw agent result dict */
	data: z.record(z.string(), z.unknown())
});

export type ResultPayload = z.infer<typeof ResultPayload>;
