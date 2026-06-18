---
title: Box-proxy dev harness for the UI
date: 2026-06-17
status: draft
area: ui
---

# Box-proxy dev harness for the UI

## Problem

Forge runs on a single NixOS box and is normally developed on that box. When
working with browser-based design tools (Paper, etc.) it is convenient to run
the SvelteKit dev server on a Mac instead. The frontend can already point at the
live Forge over Tailscale via the `VITE_API_PROXY` env var, but using it today
means hand-typing the full tailnet URL on every `pnpm dev`, and the variable is
read straight off `process.env` so a per-machine `.env.local` is ignored. The
goal is a one-command, per-machine hybrid dev setup with nothing box-specific
running on the Mac.

## Goal

On the Mac, plain `pnpm dev` launches the UI dev server (port 5180) proxying
`/api` and `/health` to the live Forge on the box
(`https://ardent-forge.feist-gondola.ts.net`), giving real data and real agents
while iterating on the frontend. On the box (and in CI), `pnpm dev`/builds
continue to default to `http://localhost:7030` with no change.

## Non-goals (YAGNI)

- No local Python backend on the Mac.
- No Zellij / `op` (1Password) / `tailscale serve` stubs or shims.
- No mock-data dev mode (the Playwright mock fallback already exists and is
  untouched).
- No app-level auth — Tailscale handles network access.

## Approach

Approach A ("`.env.local` + `loadEnv`"), chosen over an explicit `dev:box` npm
script because it keeps `pnpm dev` as the single command, keeps the tailnet host
out of committed files, and naturally degrades to localhost everywhere the file
is absent.

### Changes

1. **`ui/vite.config.ts`** — resolve the proxy target through Vite's `loadEnv`
   so a gitignored `.env.local` is honored, while keeping the current precedence
   and localhost default. Resolution order for the proxy target:
   1. `process.env.VITE_API_PROXY` (explicit inline env var still wins, so the
      documented `VITE_API_PROXY=... pnpm dev` form keeps working)
   2. `VITE_API_PROXY` loaded from `ui/.env*` files via `loadEnv(mode, cwd, "")`
   3. `http://localhost:7030` default

   `defineConfig` becomes the function form `defineConfig(({ mode }) => ({ ... }))`
   so `mode` is available to `loadEnv`. The empty prefix arg (`""`) is required
   because `loadEnv` otherwise only exposes `VITE_`-prefixed vars to its return
   value — `VITE_API_PROXY` is already `VITE_`-prefixed so the default prefix
   also works, but passing `""` is explicit and future-proof.

2. **`.gitignore`** — add `ui/.env.local` (and `ui/.env.*.local`) so the
   per-machine file is never committed. (SvelteKit's scaffold does not ignore it
   here; the repo's root `.gitignore` currently has no `.env` pattern.)

3. **`ui/.env.local.example`** — a committed template showing the one line:
   `VITE_API_PROXY=https://ardent-forge.feist-gondola.ts.net`. Developers copy it
   to `.env.local` on their Mac. Keeping the real host only in an example file
   (not in the live config) matches the existing convention of keeping the
   tailnet domain out of committed live config (cf. `nix/locals.nix`).

4. **`README.md`** — add a short "Hybrid dev against the box" subsection under
   the frontend instructions: copy `ui/.env.local.example` to `ui/.env.local`,
   ensure the Mac is on the tailnet, run `pnpm dev`.

## Data flow

```
Mac browser  →  Vite dev server (5180)  →  [proxy /api,/health]
             →  https://ardent-forge.feist-gondola.ts.net  (Tailscale + Caddy)
             →  Forge (box, :7030)
```

Chat responses stream as plain chunked HTTP (`StreamingResponse`,
`text/plain`), which passes through the Vite HTTP proxy unchanged — no
websocket/`ws: true` handling needed.

## Verification

- On the box with no `.env.local`: `pnpm dev` proxies to `localhost:7030`
  (unchanged behavior); `pnpm build` and CI unaffected.
- With `ui/.env.local` present: `pnpm dev` proxies `/api` to the tailnet host;
  loading the app shows live data from the box and chat streams.
- `VITE_API_PROXY=http://localhost:7030 pnpm dev` still overrides the file.
- `git status` shows `.env.local` ignored; `.env.local.example` tracked.
