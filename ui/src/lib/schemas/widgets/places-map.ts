import { z } from 'zod';

/**
 * places.map — pinned locations on an OpenStreetMap tile layer.
 * Leaflet + OSM per memory/project_map_widget_osm.md.
 */

export const LatLng = z.object({ lat: z.number(), lng: z.number() });
export type LatLng = z.infer<typeof LatLng>;

export const PlaceResult = z.object({
	id: z.string(),
	name: z.string(),
	neighbourhood: z.string().optional(),
	descriptor: z.string().optional(),
	distanceLabel: z.string(),
	etaLabel: z.string(),
	coord: LatLng,
	tags: z.array(z.string()).default([]),
	rating: z.string().optional()
});
export type PlaceResult = z.infer<typeof PlaceResult>;

export const PlacesMapPayload = z.object({
	tool: z.literal('places.map'),
	query: z.string(),
	centre: LatLng,
	zoom: z.number().int().min(1).max(20).default(13),
	results: z.array(PlaceResult).min(1)
});
export type PlacesMapPayload = z.infer<typeof PlacesMapPayload>;
