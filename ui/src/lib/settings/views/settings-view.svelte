<script lang="ts">
	import { Display, Eyebrow, Heading, Body, Meta } from '$lib/typography';
	import { Heartbeat, ChatCircle, Lightning } from '$lib/icons';
	import ThemeToggle from '../components/theme-toggle.svelte';
	import SettingsSection from '../components/settings-section.svelte';
	import ExternalLinkCard from '../components/external-link-card.svelte';

	// Dashboards are proxied by Caddy on the same tailnet host (see nix/services/caddy.nix),
	// so relative URLs work in production. In dev they 404 — fine; this page is mostly
	// useful on the deployed box.
	const dashboards = [
		{
			title: 'Grafana',
			description: 'Metrics, task throughput, agent runs, system health.',
			href: '/svc/grafana/',
			icon: Heartbeat
		},
		{
			title: 'Prometheus',
			description: 'Raw metrics scrape and ad-hoc PromQL.',
			href: '/svc/prometheus/',
			icon: Lightning
		},
		{
			title: 'NTFY',
			description: 'Push notifications and deploy alerts.',
			href: '/svc/ntfy/',
			icon: ChatCircle
		}
	];

	const upcoming = [
		'Notification preferences (which events page NTFY)',
		'Default agent for dispatched tasks',
		'Memory & notebook locations',
		'Linear team & project defaults',
		'Connector credentials manager'
	];
</script>

<div class="flex flex-col gap-7 px-14 pt-9 pb-12 max-w-[920px] mx-auto">
	<header class="flex flex-col gap-1.5 pb-[14px] border-b border-[var(--color-border)]">
		<Eyebrow>SETTINGS</Eyebrow>
		<Display size="lg">Preferences</Display>
		<Heading size="sm" italic>Tune how the forge looks and where it points.</Heading>
	</header>

	<div class="flex flex-col">
		<SettingsSection
			eyebrow="APPEARANCE"
			title="Theme"
			description="Light, dark, or follow your operating system. Saved locally to this browser."
		>
			<ThemeToggle />
		</SettingsSection>

		<SettingsSection
			eyebrow="DASHBOARDS"
			title="External tools"
			description="Operational surfaces hosted alongside the forge on this tailnet host."
		>
			<div class="flex flex-col gap-2.5">
				{#each dashboards as d (d.href)}
					<ExternalLinkCard
						title={d.title}
						description={d.description}
						href={d.href}
						icon={d.icon}
					/>
				{/each}
			</div>
		</SettingsSection>

		<SettingsSection
			eyebrow="COMING SOON"
			title="More settings"
			description="Sketches of what this page will grow into."
		>
			<ul class="flex flex-col gap-1.5 pl-1">
				{#each upcoming as item (item)}
					<li class="flex items-center gap-2">
						<span class="font-mono text-[var(--color-graphite)] text-[11px]">◇</span>
						<Body size="sm" muted>{item}</Body>
					</li>
				{/each}
			</ul>
		</SettingsSection>

		<SettingsSection eyebrow="ABOUT" title="Ardent Forge">
			<div class="flex flex-col gap-1">
				<Meta size="sm">Personal agentic platform · self-hosted on NixOS.</Meta>
				<Meta size="xs">UI built with SvelteKit + Tailwind. Backend: FastAPI + SQLite.</Meta>
			</div>
		</SettingsSection>
	</div>
</div>
