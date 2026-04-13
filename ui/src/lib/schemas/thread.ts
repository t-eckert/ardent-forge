import { z } from 'zod';
import { Id, IsoDate } from './primitives';

/** A conversation between the user and the Forge — the unit shown in the Threads surface. */
export const Thread = z.object({
	id: Id,
	title: z.string(),
	/** One-line summary for preview rows */
	preview: z.string(),
	/** Tool capabilities exposed in this thread (shown as a chip) */
	kind: z.enum(['code+tools', 'health+tools', 'places+tools', 'chat']),
	lastActivityIso: IsoDate,
	unread: z.boolean().default(false),
	/** Widget count — shown as "3 widgets" chip when > 0 */
	widgetCount: z.number().int().nonnegative().default(0)
});
export type Thread = z.infer<typeof Thread>;
