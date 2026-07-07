import { test as base } from '@playwright/test';

/**
 * Route loaders silently fall back to mock data when the Forge API is
 * unreachable. That's fine for a UI-only smoke layer, but it should be loud:
 * every test gets an `api-mode` annotation recording whether it ran against
 * the live API or mocks, and setting E2E_REQUIRE_API=1 turns an unreachable
 * API into a hard failure instead of a silently-mocked pass.
 */
export const test = base.extend<{ apiMode: 'live' | 'mocked' }>({
	apiMode: [
		async ({ request, baseURL }, use, testInfo) => {
			let mode: 'live' | 'mocked' = 'mocked';
			try {
				const res = await request.get(`${baseURL}/health`, { timeout: 2_000 });
				if (res.ok()) mode = 'live';
			} catch {
				// unreachable → mocked
			}
			testInfo.annotations.push({ type: 'api-mode', description: mode });
			if (mode === 'mocked' && process.env.E2E_REQUIRE_API) {
				throw new Error(
					'E2E_REQUIRE_API is set but the Forge API is unreachable — ' +
						'tests would silently pass against mock data.'
				);
			}
			await use(mode);
		},
		{ auto: true }
	]
});

export { expect } from '@playwright/test';
