import { z } from 'zod';

/**
 * weather.forecast — current conditions + 8-day daily forecast for a location.
 * Emitted whenever the model calls the get_weather tool.
 */

export const DayForecast = z.object({
	/** ISO date, e.g. "2026-04-15" */
	date: z.string(),
	minC: z.number(),
	maxC: z.number(),
	description: z.string()
});

export const WeatherPayload = z.object({
	tool: z.literal('weather.forecast'),
	location: z.string(),
	/** ISO timestamp or short label for when the reading was taken */
	asOf: z.string(),
	currentC: z.number(),
	summary: z.string(),
	daily: z.array(DayForecast).min(1).max(8)
});

export type DayForecast = z.infer<typeof DayForecast>;
export type WeatherPayload = z.infer<typeof WeatherPayload>;
