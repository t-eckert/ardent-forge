import { z } from 'zod';
import { CodeDiffPayload } from './code-diff';
import { WeatherPayload } from './weather';
import { PurchasesPayload } from './purchases';
import { WorkoutsPayload } from './workouts';
import { PlacesMapPayload } from './places-map';

export * from './code-diff';
export * from './weather';
export * from './purchases';
export * from './workouts';
export * from './places-map';

/**
 * Discriminated union of every widget payload the assistant can emit.
 * Add new widget schemas here so `widget-host` stays exhaustive.
 */
export const WidgetPayload = z.discriminatedUnion('tool', [
	CodeDiffPayload,
	WeatherPayload,
	PurchasesPayload,
	WorkoutsPayload,
	PlacesMapPayload
]);
export type WidgetPayload = z.infer<typeof WidgetPayload>;
