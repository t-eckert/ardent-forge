import { z } from 'zod';
import { Id, IsoDate } from './primitives';

export const TaskStatus = z.enum(['open', 'in-progress', 'review', 'blocked', 'done']);
export type TaskStatus = z.infer<typeof TaskStatus>;

export const TaskCategory = z.enum(['work', 'health', 'art', 'errand', 'ritual', 'review']);
export type TaskCategory = z.infer<typeof TaskCategory>;

export const Task = z.object({
	id: Id,
	title: z.string(),
	status: TaskStatus,
	category: TaskCategory,
	dueIso: IsoDate.optional(),
	/** Free-form destination — e.g. "Coordinator" or "Painting trip" */
	context: z.string().optional()
});
export type Task = z.infer<typeof Task>;
