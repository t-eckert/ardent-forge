import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * E2E smoke tests for the Ardent Forge UI.
 *
 * Route loaders fall back to mock data when the API is unreachable, so these
 * tests can run without a live forge — but never silently: smoke tests are
 * annotated with their api-mode, and E2E_REQUIRE_API=1 fails the run instead
 * of falling back (see e2e/fixtures.ts). visual.spec.ts deliberately stays on
 * mocks for deterministic screenshots.
 */

// Mirror vite.config.ts: when a Tailscale cert is present in ui/.certs the
// dev server terminates TLS, so the webServer probe and browser must speak
// HTTPS (with the ts.net-named cert ignored for 127.0.0.1).
const dirname = path.dirname(fileURLToPath(import.meta.url));
const certHost = 'ardent-forge.feist-gondola.ts.net';
const hasCerts =
	fs.existsSync(path.join(dirname, '.certs', `${certHost}.crt`)) &&
	fs.existsSync(path.join(dirname, '.certs', `${certHost}.key`));
const baseURL = `${hasCerts ? 'https' : 'http'}://127.0.0.1:5180`;

export default defineConfig({
	testDir: './e2e',
	timeout: 30_000,
	fullyParallel: true,
	reporter: 'list',
	use: {
		baseURL,
		ignoreHTTPSErrors: hasCerts,
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
		url: baseURL,
		ignoreHTTPSErrors: hasCerts,
		reuseExistingServer: !process.env.CI,
		timeout: 60_000
	}
});
