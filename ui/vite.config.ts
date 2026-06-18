/// <reference types="vitest/config" />
import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { storybookTest } from '@storybook/addon-vitest/vitest-plugin';
const dirname = typeof __dirname !== 'undefined' ? __dirname : path.dirname(fileURLToPath(import.meta.url));

// More info at: https://storybook.js.org/docs/next/writing-tests/integrations/vitest-addon
// Proxy target for /api and /health during `pnpm dev`.
//
// Resolution order:
//   1. process.env.VITE_API_PROXY  (inline: `VITE_API_PROXY=... pnpm dev`)
//   2. VITE_API_PROXY from ui/.env* files (loadEnv) — e.g. a per-machine,
//      gitignored ui/.env.local pointing at the box over Tailscale:
//        VITE_API_PROXY=https://ardent-forge.<tailnet>.ts.net
//   3. http://localhost:7030  (box / CI default)
export default defineConfig(({ mode }) => {
  const fileEnv = loadEnv(mode, dirname, "");
  const apiProxyTarget =
    process.env.VITE_API_PROXY ?? fileEnv.VITE_API_PROXY ?? "http://localhost:7030";

  return {
    plugins: [sveltekit()],
    server: {
      proxy: {
        "/api": { target: apiProxyTarget, changeOrigin: true, secure: true },
        "/health": { target: apiProxyTarget, changeOrigin: true, secure: true }
      }
    },
    test: {
      projects: [{
        extends: true,
        test: {
          include: ["src/**/*.{test,spec}.{js,ts}"],
          environment: "happy-dom",
          globals: true
        }
      }, {
        extends: true,
        plugins: [
        // The plugin will run tests for the stories defined in your Storybook config
        // See options at: https://storybook.js.org/docs/next/writing-tests/integrations/vitest-addon#storybooktest
        storybookTest({
          configDir: path.join(dirname, '.storybook')
        })],
        test: {
          name: 'storybook',
          browser: {
            enabled: true,
            headless: true,
            provider: 'playwright',
            instances: [{
              browser: 'chromium'
            }]
          }
        }
      }]
    }
  };
});