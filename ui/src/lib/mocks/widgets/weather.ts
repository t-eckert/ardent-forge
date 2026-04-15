import { WeatherPayload, type WeatherPayload as WeatherPayloadT } from '$lib/schemas/widgets/weather';

export function makeWeather(overrides: Partial<WeatherPayloadT> = {}): WeatherPayloadT {
	return WeatherPayload.parse({
		tool: 'weather.forecast',
		location: 'Ottawa',
		asOf: '2026-04-15T14:07:00+00:00',
		currentC: 18,
		summary: 'clear sky',
		daily: [
			{ date: '2026-04-15', minC: 8, maxC: 18, description: 'clear sky' },
			{ date: '2026-04-16', minC: 10, maxC: 21, description: 'few clouds' },
			{ date: '2026-04-17', minC: 12, maxC: 23, description: 'scattered clouds' },
			{ date: '2026-04-18', minC: 9, maxC: 17, description: 'light rain' },
			{ date: '2026-04-19', minC: 7, maxC: 14, description: 'overcast clouds' },
			{ date: '2026-04-20', minC: 6, maxC: 15, description: 'clear sky' },
			{ date: '2026-04-21', minC: 8, maxC: 19, description: 'few clouds' },
			{ date: '2026-04-22', minC: 11, maxC: 22, description: 'clear sky' }
		],
		...overrides
	});
}
