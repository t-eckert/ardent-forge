import { z } from 'zod';
import { Id, IsoDate } from './primitives';

/**
 * Todo — a personal to-do, primarily managed by the user in the Notebook.
 *
 * Distinct from backend Task (see ./task.ts) — Todos are checklist items
 * on the Today canvas, in the daily log, in Library/Todos. Backend Tasks
 * are units of agentic work with stages, artifacts, and resolution posts.
 */

export const TodoStatus = z.enum(['open', 'in-progress', 'review', 'blocked', 'done']);
export type TodoStatus = z.infer<typeof TodoStatus>;

export const TodoCategory = z.enum(['work', 'health', 'art', 'errand', 'ritual', 'review']);
export type TodoCategory = z.infer<typeof TodoCategory>;

export const Todo = z.object({
	id: Id,
	title: z.string(),
	status: TodoStatus,
	category: TodoCategory,
	dueIso: IsoDate.optional(),
	/** Free-form destination — e.g. "Coordinator" or "Painting trip" */
	context: z.string().optional()
});
export type Todo = z.infer<typeof Todo>;
