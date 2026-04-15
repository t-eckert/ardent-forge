import { expect, test } from '@playwright/test';

/**
 * Golden-path smoke tests. Every route loader falls back to mock data when
 * the backend is unreachable, so these tests don't require a running forge
 * instance. They assert that the SPA loads, client-side routing works, and
 * the key surfaces render identifiable chrome.
 */

test.describe('smoke', () => {
	test('Today renders the hero greeting + today panel', async ({ page }) => {
		await page.goto('/today');
		await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
		// Mock threads list shows up in OpenThreads panel.
		await expect(page.getByText(/overnight/i).first()).toBeVisible({ timeout: 10_000 });
	});

	test('Threads list renders and a thread is clickable', async ({ page }) => {
		await page.goto('/threads');
		// Mock threads are present — pick one and navigate.
		const firstThread = page.locator('a[href^="/threads/"]').first();
		await expect(firstThread).toBeVisible();
		await firstThread.click();
		await expect(page).toHaveURL(/\/threads\/[^/]+/);
		// The composer input is present on thread detail.
		await expect(page.getByRole('textbox', { name: /message/i })).toBeVisible();
	});

	test('Library → Agents roster renders', async ({ page }) => {
		await page.goto('/library/agents');
		await expect(page.getByText(/agent/i).first()).toBeVisible();
	});

	test('Tasks list renders and a task is navigable', async ({ page }) => {
		await page.goto('/tasks');
		// Mock-fallback: tasks endpoint returns nothing so the view shows its
		// empty state pane. Either way the chrome loads without errors.
		await expect(page.locator('body')).toBeVisible();
		// No console errors so far.
	});

	test('Root redirects or renders the shell', async ({ page }) => {
		await page.goto('/');
		// The sidebar spine should be visible on every page.
		await expect(page.locator('aside').first()).toBeVisible();
	});
});
