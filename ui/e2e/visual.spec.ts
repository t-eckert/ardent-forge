import { expect, test } from '@playwright/test';

/**
 * Visual regression — full-page screenshots of every key surface.
 *
 * Runs against the Vite dev server with mock fallbacks, so the output is
 * deterministic (modulo font hinting + platform rasterisation). Baselines
 * are committed under e2e/__screenshots__/ and produced on first run.
 *
 * Regenerate after an intentional design change:
 *     pnpm test:e2e --update-snapshots
 */

// Pin the viewport so the baseline is comparable across runs. A consistent
// window size matters far more than exact device emulation here.
test.use({ viewport: { width: 1440, height: 900 } });

const PAGES: Array<{ path: string; name: string; waitFor?: string }> = [
	{ path: '/today', name: 'today' },
	{ path: '/threads', name: 'threads-list' },
	{ path: '/tasks', name: 'tasks-list' },
	{ path: '/library/agents', name: 'library-agents' },
	{ path: '/library/connectors', name: 'library-connectors' },
	{ path: '/library/memory', name: 'library-memory' },
	{ path: '/library/fields', name: 'library-fields' }
];

for (const p of PAGES) {
	test(`visual · ${p.name}`, async ({ page }) => {
		await page.goto(p.path);
		// Give the SPA a beat to hydrate + fonts to settle. Networkidle is
		// brittle (the loader's failed fetches retry); a fixed short wait is
		// more reliable and still fast.
		await page.waitForLoadState('domcontentloaded');
		await page.waitForTimeout(500);
		await expect(page).toHaveScreenshot(`${p.name}.png`, {
			fullPage: true,
			// Generous threshold — font anti-aliasing drift across OSes is
			// louder than any real regression worth catching here.
			maxDiffPixelRatio: 0.02
		});
	});
}
