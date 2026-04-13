import { WeatherPayload, type WeatherPayload as WeatherPayloadT } from '$lib/schemas/widgets/weather';

export function makeWeather(overrides: Partial<WeatherPayloadT> = {}): WeatherPayloadT {
	return WeatherPayload.parse({
		tool: 'weather.forecast',
		location: 'Ottawa',
		asOf: '14:07',
		currentC: 18,
		summary: 'Clearing · warm front',
		hours: [
			{ label: '15:00', tempC: 19 },
			{ label: '16:00', tempC: 21 },
			{ label: '17:00', tempC: 22 },
			{ label: '18:00', tempC: 20 },
			{ label: '19:00', tempC: 17 }
		],
		...overrides
	});
}
