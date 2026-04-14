import type { PageLoad } from './$types';
import { api, type Connector } from '$lib/api/typed';

export const ssr = false;

type Health = 'live' | 'synced' | 'stale' | 'failing' | 'unknown';

const FALLBACK: Array<Connector & { health: Health }> = [
	{
		name: 'weather',
		health: 'unknown',
		tools: [{ name: 'get_weather', description: 'Current weather + 8-day forecast', long_running: false }]
	}
];

export const load: PageLoad = async () => {
	try {
		const [connectors, health] = await Promise.all([
			api.connectors.list(),
			api.connectors.health().catch(() => ({}) as Record<string, boolean>)
		]);
		const enriched = connectors.map((c) => ({
			...c,
			health: ((): Health => {
				const h = (health as Record<string, boolean>)[c.name];
				if (h === true) return 'live';
				if (h === false) return 'failing';
				return 'unknown';
			})()
		}));
		return { connectors: enriched };
	} catch (err) {
		console.warn('/api/connectors unavailable — using fallback', err);
		return { connectors: FALLBACK, apiError: String(err) };
	}
};
