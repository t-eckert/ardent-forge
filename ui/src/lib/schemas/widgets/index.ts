import { z } from 'zod';
import { CodeDiffPayload } from './code-diff';
import { WeatherPayload } from './weather';
import { ResultPayload } from './result';
import { CodeResultPayload } from './code-result';

export * from './code-diff';
export * from './weather';
export * from './result';
export * from './code-result';

/**
 * Discriminated union of every widget payload the assistant can emit.
 * Add new widget schemas here so `widget-host` stays exhaustive.
 */
export const WidgetPayload = z.discriminatedUnion('tool', [
    CodeDiffPayload,
    WeatherPayload,
    ResultPayload,
    CodeResultPayload
]);
export type WidgetPayload = z.infer<typeof WidgetPayload>;
