import { defineConfig, devices } from '@playwright/test';

/**
 * E2E smoke tests for the Ardent Forge UI.
 *
 * These tests run against the Vite dev server with no backend reachable —
 * every route loader falls back to its mock data when the API is
 * unavailable, so the UI's golden paths still render. This is deliberately
 * a lightweight smoke layer; full end-to-end flows (chat → dispatch →
 * resolution) are exercised via the runbook on the box.
 */
export default defineConfig({
	testDir: './e2e',
	timeout: 30_000,
	fullyParallel: true,
	reporter: 'list',
	use: {
		baseURL: 'http://127.0.0.1:5180',
		trace: 'on-first-retry'
	},
	projects: [
		{
			name: 'chromium',
			use: { ...devices['Desktop Chrome'] }
		}
	],
	webServer: {
		command: 'pnpm dev --port 5180 --strictPort --host 127.0.0.1',
		url: 'http://127.0.0.1:5180',
		reuseExistingServer: !process.env.CI,
		timeout: 60_000
	}
});
