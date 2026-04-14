<script lang="ts">
	import { MemoryLibrary } from '$lib/library';

	// Stand-in — Phase M will fetch /api/memory.
	const entries = [
		{
			filename: 'user_role.md',
			slug: 'user_role',
			name: 'User role',
			description: 'Software engineer at Redpanda, currently building Ardent Forge',
			type: 'user' as const,
			body: 'Focus on async Python + TypeScript + NixOS.',
			updated_at: '2026-04-13'
		},
		{
			filename: 'numbers_mono.md',
			slug: 'numbers_mono',
			name: 'Numbers always mono',
			description: 'All numeric values render in JetBrains Mono; Playfair is for words only',
			type: 'feedback' as const,
			body: 'Enforced via the <Stat> component.',
			updated_at: '2026-04-12'
		},
		{
			filename: 'map_widget_osm.md',
			slug: 'map_widget_osm',
			name: 'Map widget uses OpenStreetMap',
			description: 'places.map widget must render on OSM tiles (Leaflet/MapLibre + Nominatim)',
			type: 'project' as const,
			body: 'No Google or Mapbox.',
			updated_at: '2026-04-12'
		}
	];
</script>

<MemoryLibrary {entries} />
