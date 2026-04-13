import { z } from 'zod';
import { CodeDiffPayload } from './code-diff';

export * from './code-diff';

/**
 * Discriminated union of every widget payload the assistant can emit.
 * Add new widget schemas here so `widget-host` stays exhaustive.
 */
export const WidgetPayload = z.discriminatedUnion('tool', [CodeDiffPayload]);
export type WidgetPayload = z.infer<typeof WidgetPayload>;
