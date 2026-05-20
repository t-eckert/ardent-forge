---
name: ui-dev-platform-alignment
description: Bring the SvelteKit UI in line with the developer-toolbox direction. Remove stale personal-assistant remnants (fields, todos, purchases/workouts/places-map widgets) and surface dev-platform capabilities — a top-level Repos page enriched with Tailscale dev-server links, a new Workspaces page listing live Zellij sessions, a read-only Notebook browser, and a rewired Today dashboard. Full-stack: adds the backend endpoints each surface needs.
type: design
---

# UI Alignment with the Dev-Platform Direction

## Why

The backend pivoted to a developer-toolbox control plane (see `2026-05-19-dev-toolbox-pivot.md`), but the UI still reflects the earlier personal-assistant era. It ships widgets and API calls with no backend behind them, and it doesn't surface the capabilities that now define the platform (dev servers, live Zellij sessions, the agent roster). This effort closes that gap in both directions: remove what's dead, surface what's live.

The user's framing: "This is now an agentic dev platform." Repos and the live development sessions running against them are the centerpiece and deserve to be first-class destinations, not nested inside Library. The notebook remains a read-only reference you can browse.

## Current state (the drift)

**Stale in the UI — no backend behind it:**
- Widgets `purchases` (`finance.purchases`), `workouts` (`health.workouts`), `places-map` (`places.map`) — no connector emits these.
- `lib/api/typed.ts` calls `/api/fields` and `/api/todos` — neither router is registered in `forge/main.py`.
- The whole `lib/fields` UI module.
- Unregistered backend modules `forge/api/fields.py` and `forge/api/todos.py`.

**Live in the backend — not surfaced in the UI:**
- Repos carry `dev_port`; `TailscaleServe` exposes each as `https://<machine>.<tailnet>:<dev_port>/`.
- The Code agent stashes `zellij_session` and `attach_cmd` in `task.result` (already serialized by the task API via `model_dump`).
- The agent roster: Echo / Code / Plan / Tickets.
- The speedtest connector records bandwidth history in `speedtest_results`.

**Live and kept:** the weather widget/connector (restored in commit 98fb1ba).

## Information architecture

The sidebar spine becomes seven items:

```
Today · Threads · Workspaces · Repos · Tasks · Notebook · Library
```

- **Workspaces** = live development sessions (running Zellij sessions + their dev servers). What's running right now.
- **Repos** = the code catalog (git repos in `~/Repos` with `repo.yaml`). Static config + metadata.
- **Notebook** = read-only browse of the Obsidian vault.
- **Library** keeps the meta surfaces: Agents, Connectors, Memory, Schedules, Log.

Implementation: update the `Spine` type and `spineFromPath` in `ui/src/lib/chrome/state/chrome.state.svelte.ts`, and add the items/icons to `ui/src/lib/chrome/components/sidebar.svelte`. Breadcrumbs derive from the path automatically.

## Delivery strategy

Vertical slices, destination by destination. Each slice ships backend + UI together and is independently shippable, testable, and demoable on the box. Order: Cleanup → Repos → Workspaces → Notebook → Today.

## Slice 0 — Cleanup

No new behavior; removes dead code so the UI matches the backend.

**Frontend:**
- Delete widget dirs `lib/widgets/purchases`, `lib/widgets/workouts`, `lib/widgets/places-map`.
- Remove their exports from `lib/widgets/index.ts`, their cases from `lib/widgets/kernel/widget-host.svelte`, their schemas from `lib/schemas/widgets/` and the `WidgetPayload` union, and any mocks/stories.
- Delete the `lib/fields` module.
- Remove the `fields` and `todos` clients from `lib/api/typed.ts` (and any callers).

**Backend:**
- Delete `forge/api/fields.py` and `forge/api/todos.py` (both unregistered).

**Done when:** `pnpm check` and `pnpm build` pass, no references to removed symbols remain, backend tests pass.

## Slice 1 — Repos (enrich, promote to `/repos`)

**Backend (`forge/api/repos.py`, `forge/repos/`):**
- Extend the per-repo API payload with:
  - `claude_label` (from `RepoConfig`).
  - `dev_url`: the computed `https://<machine>.<tailnet>:<dev_port>/` URL when `dev_port` is set and Tailscale is available; `null` otherwise.
  - `env_keys`: the *keys* of the repo's env map only. **Never expose env values** — they hold `op://` secret references.
- Add a helper to resolve the tailnet hostname once at startup (e.g. parse `tailscale status --json` → self DNSName) and make it available to the repos API. If unavailable, `dev_url` is `null`.

**Frontend (`/repos` route, `lib/repos` module):**
- Per-repo card/row: name, default branch, `dev_port`, a dev-server link that opens `dev_url` in a new tab, a `claude_label` badge, and the `env_keys` list.
- Move the existing repos surface out of Library to the top-level route.

**Done when:** `/api/repos` returns the enriched shape, the page renders real repos, dev-server links open the Tailscale URL.

## Slice 2 — Workspaces (new, `/workspaces`)

**Backend:**
- Add `ZellijRunner.list_sessions()` that runs `zellij list-sessions` and parses session names + state (created/exited). Returns structured records.
- Add a `/api/workspaces` endpoint: list live sessions named `agent-<task-id>`, join each to its task (title, repo, status) from the store, and include the `attach_cmd`.

**Frontend (`/workspaces` route, `lib/workspaces` module):**
- List live sessions: repo, task title, task status, a copyable attach command, and a link to the Task detail page.
- Clean empty state when nothing is running.

**Done when:** `/api/workspaces` returns live sessions joined to tasks, the page lists them with working copy + task links, empty state shows when idle.

## Slice 3 — Notebook (read-only browse, `/notebook`)

**Backend:** endpoints already exist (`/api/notebook/list`, `/read`, `/search`). Drop the stale `/api/notebook/counts` (its `Log/Wiki/Fields/People/Collections` shape is unused by the new UI).

**Frontend (`/notebook` route, `lib/notebook` module):**
- Directory browser (drills via `/list`), rendered markdown view (via `/read`), and a search box (via `/search`). Strictly read-only — no edit affordances.

**Done when:** the page browses the vault, renders pages, and searches; no write paths exist.

## Slice 4 — Today (rewire dashboard)

**Backend:** add a tiny `/api/speedtest/latest` endpoint returning the most recent `speedtest_results` row.

**Frontend (`today` view + loader):**
- Drop removed data sources (fields/todos/etc.).
- Compose from live data: active/queued tasks, a **dev-servers strip** (repos with a `dev_url`), an **active-workspaces** summary (from `/api/workspaces`), open threads, the weather card, and a small latest-speedtest stat.

**Done when:** the dashboard loads against live endpoints with no calls to removed routes, and surfaces dev servers + active workspaces.

## Testing

- **Backend (pytest):** new tests for `/api/workspaces` (mock `zellij list-sessions`; assert task join + `attach_cmd`), repos enrichment (`dev_url`, `env_keys` excludes values, `claude_label`), and `/api/speedtest/latest`.
- **Frontend:** update the `WidgetPayload` union / adapters tests after widget removals; add Storybook stories for the Repos, Workspaces, and Notebook views; add Playwright smoke coverage for the new routes (mock fallback when the API is unreachable).
- Run `uv run pytest -q`, `pnpm check`, `pnpm build` before declaring each slice done.

## Out of scope / future

- **Taskfile integration** — run a repo's Taskfile tasks directly from the UI. Noted by the user as a side idea for later; explicitly not part of this effort.

## Security notes

- Repos API must expose env **keys only**, never values (`op://` secret references must not leak to the client).
- The Notebook surface is read-only; do not add write endpoints or edit affordances.
