import { z } from 'zod';
import { Id, IsoDate } from './primitives';
import { WidgetPayload } from './widgets';

/**
 * Task — a unit of agentic work processed by an agent. Distinct from Todo.
 *
 * Matches the backend /api/tasks JSON shape. A Task has stages, status
 * transitions, optional artifact widgets, and may be linked to an origin
 * thread (where Forge posts its resolution message on completion).
 */

export const TaskStatus = z.enum([
	'queued',
	'triaging',
	'executing',
	'verifying',
	'delivering',
	'completed',
	'failed'
]);
export type TaskStatus = z.infer<typeof TaskStatus>;

export const TaskKind = z.enum(['code', 'plan', 'tickets', 'echo']);
export type TaskKind = z.infer<typeof TaskKind>;

export const TaskStep = z.object({
	label: z.string(),
	atIso: IsoDate,
	durationLabel: z.string().optional(),
	state: z.enum(['done', 'waiting', 'failed'])
});
export type TaskStep = z.infer<typeof TaskStep>;

export const Task = z.object({
	id: Id,
	/** Agent task_type, e.g. "code", "plan", "echo" */
	type: z.string(),
	status: TaskStatus,
	source: z.string(),
	source_id: z.string().nullable().optional(),
	repo: z.string().nullable().optional(),
	title: z.string(),
	description: z.string(),
	/** Stage-specific data produced during execute (worktree_path, branch, etc.) */
	handler_data: z.record(z.string(), z.unknown()).default({}),
	/** Final aggregated result — available after completed */
	result: z.record(z.string(), z.unknown()).nullable().optional(),
	retries: z.number().int().default(0),
	created_at: IsoDate,
	updated_at: IsoDate,
	completed_at: IsoDate.nullable().optional(),
	/** Thread that spawned this task, if any. Drives resolution post-back. */
	origin_thread_id: z.string().nullable().optional(),
	/** Threads that reference this task without having spawned it */
	referenced_by_thread_ids: z.array(z.string()).default([])
});
export type Task = z.infer<typeof Task>;

export const TaskArtifact = z.object({
	label: z.string(),
	payload: WidgetPayload
});
export type TaskArtifact = z.infer<typeof TaskArtifact>;
