<script lang="ts">
	import { ConnectorsRoster } from '$lib/library';

	// Static stand-in; Phase M points this at /api/connectors + /api/connectors/health.
	const connectors = [
		{
			name: 'weather',
			health: 'live' as const,
			tools: [
				{ name: 'get_weather', description: 'Current weather + 8-day forecast', long_running: false }
			]
		},
		{
			name: 'notebook',
			health: 'synced' as const,
			tools: [
				{ name: 'notebook.read', description: 'Read a vault page by path', long_running: false },
				{ name: 'notebook.search', description: 'Ripgrep across the vault', long_running: false }
			]
		},
		{
			name: 'github',
			health: 'unknown' as const,
			tools: [
				{ name: 'git.open_pr', description: 'Open a PR from a worktree', long_running: true }
			]
		},
		{
			name: 'linear',
			health: 'unknown' as const,
			tools: [
				{ name: 'linear.create_project', description: 'Create a project + issues', long_running: false }
			]
		}
	];
</script>

<ConnectorsRoster {connectors} />
