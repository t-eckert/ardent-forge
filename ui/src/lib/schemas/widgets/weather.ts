import { z } from 'zod';

/**
 * weather.forecast — current conditions + hourly forecast for a location.
 * Emitted whenever the model needs to anchor a response in actual weather.
 */

export const HourForecast = z.object({
	/** Hour label, e.g. "15:00" */
	label: z.string(),
	tempC: z.number()
});

export const WeatherPayload = z.object({
	tool: z.literal('weather.forecast'),
	location: z.string(),
	/** Display timestamp (when the reading was taken) */
	asOf: z.string(),
	currentC: z.number(),
	summary: z.string(),
	hours: z.array(HourForecast).min(3).max(12)
});

export type HourForecast = z.infer<typeof HourForecast>;
export type WeatherPayload = z.infer<typeof WeatherPayload>;
