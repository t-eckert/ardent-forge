/// <reference types="vitest/config" />
import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";
import fs from 'node:fs';
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

  // Optional HTTPS for tailnet access. `.ts.net` is HSTS-preloaded, so browsers
  // force HTTPS for the MagicDNS name — plain HTTP won't load. If a Tailscale
  // cert is present (see ui/.certs, gitignored), terminate TLS in Vite so the
  // dev server is reachable at https://ardent-forge.<tailnet>.ts.net:5173.
  // Generate with: cd ui/.certs && tailscale cert ardent-forge.<tailnet>.ts.net
  const certDir = path.join(dirname, ".certs");
  const certHost = "ardent-forge.feist-gondola.ts.net";
  const certPath = path.join(certDir, `${certHost}.crt`);
  const keyPath = path.join(certDir, `${certHost}.key`);
  const https =
    fs.existsSync(certPath) && fs.existsSync(keyPath)
      ? { cert: fs.readFileSync(certPath), key: fs.readFileSync(keyPath) }
      : undefined;

  return {
    plugins: [sveltekit()],
    server: {
      // Bind to the tailnet interface so the dev server is reachable at
      // https://ardent-forge.<tailnet>.ts.net:5173 from other tailnet devices.
      host: true,
      https,
      // Vite 6 rejects requests whose Host header isn't loopback; allow the
      // MagicDNS name so tailnet access isn't blocked.
      allowedHosts: [".feist-gondola.ts.net"],
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