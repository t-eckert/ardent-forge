import { z } from 'zod';

/** health.workouts — compact in-chat view of training block state + recent sessions. */

export const WorkoutSessionRow = z.object({
	dateLabel: z.string(),
	title: z.string(),
	volumeLabel: z.string(),
	intensityLabel: z.string(),
	source: z.enum(['strava', 'notebook'])
});

export const WorkoutsPayload = z.object({
	tool: z.literal('health.workouts'),
	blockLabel: z.string(),
	goal: z.string(),
	daysToEvent: z.number().int(),
	eventLabel: z.string(),
	weekVolumeLabel: z.string(),
	weekVolumeDelta: z.string().optional(),
	longRunLabel: z.string(),
	thresholdPaceLabel: z.string(),
	thresholdPaceDelta: z.string().optional(),
	recent: z.array(WorkoutSessionRow).min(1),
	sourcesLine: z.string()
});

export type WorkoutSessionRow = z.infer<typeof WorkoutSessionRow>;
export type WorkoutsPayload = z.infer<typeof WorkoutsPayload>;
