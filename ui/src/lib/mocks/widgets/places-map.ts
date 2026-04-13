import { PlacesMapPayload, type PlacesMapPayload as PlacesMapPayloadT } from '$lib/schemas/widgets/places-map';

export function makePlacesMap(overrides: Partial<PlacesMapPayloadT> = {}): PlacesMapPayloadT {
	return PlacesMapPayload.parse({
		tool: 'places.map',
		query: 'pizza · not-chain · ≤ 15 min',
		centre: { lat: 45.403, lng: -75.678 },
		zoom: 13,
		results: [
			{
				id: 'pizza-pie',
				name: 'Pizza Pie',
				neighbourhood: 'Hintonburg',
				descriptor: 'wood-fired · $$',
				distanceLabel: '0.8 km',
				etaLabel: '6 min',
				coord: { lat: 45.405, lng: -75.733 },
				tags: ['delivery', 'open ·21h'],
				rating: '4.6 ★'
			},
			{
				id: 'stella-luna',
				name: 'Stella Luna',
				neighbourhood: 'Old Ottawa South',
				descriptor: 'Neapolitan · $$',
				distanceLabel: '2.1 km',
				etaLabel: '10 min',
				coord: { lat: 45.393, lng: -75.685 },
				tags: ['delivery 35m', 'open ·22h'],
				rating: '4.8 ★'
			},
			{
				id: 'biagios',
				name: "Biagio's",
				neighbourhood: 'Westboro',
				descriptor: 'thin crust · $$',
				distanceLabel: '3.4 km',
				etaLabel: '12 min',
				coord: { lat: 45.398, lng: -75.751 },
				tags: ['pickup only', 'open ·21h30'],
				rating: '4.4 ★'
			},
			{
				id: 'the-grand',
				name: 'The Grand',
				neighbourhood: 'Little Italy',
				descriptor: 'Detroit square · $$',
				distanceLabel: '4.0 km',
				etaLabel: '14 min',
				coord: { lat: 45.412, lng: -75.711 },
				tags: ['delivery 45m', 'open ·23h'],
				rating: '4.5 ★'
			}
		],
		...overrides
	});
}
