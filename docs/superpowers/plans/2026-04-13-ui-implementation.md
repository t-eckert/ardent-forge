# UI Implementation Plan

> **Supersedes** `2026-04-10-web-ui.md`. That plan was built against the pre-IA-revision sidebar (Dashboard / Tasks / Chat / Schedule / Settings). The temporal spine (Today / Threads / Library / Agents) and ⌘K palette replace that model entirely.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement task-by-task. Steps use `- [ ]` syntax.

**Goal.** Build the SvelteKit UI for Ardent Forge, organised by domain (Galley pattern), driven by Storybook with schema-derived mocks, served as static files by the existing FastAPI backend.

**Non-goals.** Running the backend locally — see `memory/project_dev_process.md` for the three-mode dev process (Storybook / hybrid over Tailscale / deployed on the box). Integration and E2E tests run on the box, not in local dev.

**Stack.** SvelteKit 2 · Svelte 5 (runes only) · TypeScript · Tailwind CSS 4 · CVA · Bits UI · `phosphor-svelte` · Storybook 8 · Zod · `@faker-js/faker` for mock factories · Vitest · Playwright (E2E on box).

---

## Architecture

**Domain organisation.** Each life-area or feature lives in `src/lib/<domain>/` with the Galley shape:

```
<domain>/
├── components/            # .svelte + co-located .stories.ts
├── state/                 # *.state.svelte.ts (Svelte 5 runes)
├── _stories/              # wrapper story components + mock-data.ts
├── views/                 # page-level compositions
├── <domain>.test.ts       # domain-level tests
└── index.ts               # barrel exports
```

**Routes stay thin.** `src/routes/<spine>/+page.svelte` imports a view from `lib/<domain>/views/` — nothing else.

**Global shared primitives.** `src/lib/components/` and `src/lib/typography/` hold truly shared UI (Button, Chip, KeycapHint, StatusDot, Divider, Display, Heading, Body, Meta, Stat). Domain folders never import from each other — only from globals and cross-cutting libs.

**Schemas are the source of truth.** Every widget payload, API response, and mock factory comes from a single Zod schema definition in `src/lib/schemas/`. TypeScript types are inferred from schemas (`z.infer<typeof X>`). Mock factories in `src/lib/mocks/` use `faker` + the schema to produce wire-accurate data. When a backend contract changes, Storybook breaks loudly.

**Icons.** All icons via `phosphor-svelte`. The global sidebar spine is locked to `Sun` / `ChatCircle` / `Books` / `Robot` per `memory/project_phosphor_icons.md`. `src/lib/icons/index.ts` re-exports commonly-used icons with preset sizes/weights.

**Three dev modes** (per `memory/project_dev_process.md`):
- **Storybook.** `pnpm storybook` — fast, mocked, offline.
- **Hybrid.** `pnpm dev` with `VITE_API_URL=https://ardent-forge.<tailnet>.ts.net` — UI local, backend on the box.
- **Deployed.** Autodeploy on push to main.

---

## File structure

```
ui/
├── .storybook/
│   ├── main.ts
│   ├── preview.ts
│   └── theme.ts                      # Storybook theme matching mood board
├── src/
│   ├── app.css                       # Tailwind 4 + CSS custom properties (palette, type scale)
│   ├── app.d.ts
│   ├── app.html
│   ├── hooks.client.ts
│   ├── routes/
│   │   ├── +layout.svelte            # Chrome (sidebar + palette host)
│   │   ├── +layout.ts                # SSR disabled for v1; loader for user/sync status
│   │   ├── +page.svelte              # → redirect to /today
│   │   ├── today/+page.svelte        # imports TodayView
│   │   ├── threads/
│   │   │   ├── +page.svelte          # ThreadsListView
│   │   │   └── [id]/+page.svelte     # ThreadView
│   │   ├── library/
│   │   │   ├── +page.svelte          # LibraryIndex (facet picker)
│   │   │   ├── fields/+page.svelte   # FieldsIndex
│   │   │   └── fields/[slug]/+page.svelte   # FieldDetail (generic)
│   │   └── agents/
│   │       ├── +page.svelte          # AgentsList
│   │       └── [agent]/[run]/+page.svelte   # RunDetail
│   └── lib/
│       ├── api/                      # fetch wrappers (existing api.ts refactored here)
│       │   ├── client.ts
│       │   ├── errors.ts
│       │   └── index.ts
│       ├── schemas/                  # zod schemas — source of truth
│       │   ├── primitives.ts         # shared primitives (ISO date, ids, money, duration)
│       │   ├── widgets/              # one schema per widget tool (code-diff, workouts, places-map, …)
│       │   │   ├── code-diff.ts
│       │   │   ├── workouts.ts
│       │   │   ├── places-map.ts
│       │   │   ├── weather.ts
│       │   │   ├── purchases.ts
│       │   │   └── index.ts
│       │   ├── thread.ts
│       │   ├── agent.ts
│       │   ├── field.ts
│       │   ├── task.ts
│       │   └── index.ts
│       ├── types/                    # inferred types re-exported for convenience
│       │   └── index.ts              # re-exports z.infer<typeof …>
│       ├── mocks/                    # schema-driven factories
│       │   ├── widgets/
│       │   ├── thread.ts
│       │   ├── agent.ts
│       │   ├── field.ts
│       │   ├── task.ts
│       │   └── index.ts
│       ├── icons/
│       │   └── index.ts              # phosphor-svelte re-exports w/ presets
│       ├── theme/
│       │   ├── tokens.ts             # palette + spacing + radius constants
│       │   ├── theme-store.svelte.ts
│       │   └── theme-provider.svelte
│       ├── typography/               # GLOBAL typographic primitives
│       │   ├── display.svelte        # Playfair · hero titles
│       │   ├── heading.svelte        # Playfair · section titles
│       │   ├── body.svelte           # Inter · long-form prose
│       │   ├── meta.svelte           # JetBrains Mono · 10–11px labels, eyebrow-style
│       │   ├── stat.svelte           # JetBrains Mono · numeric display w/ optional unit
│       │   ├── eyebrow.svelte        # JetBrains Mono · letterspaced section tags
│       │   └── index.ts
│       ├── components/               # GLOBAL shared UI primitives
│       │   ├── button.svelte
│       │   ├── chip.svelte           # status chips, tag chips
│       │   ├── keycap-hint.svelte    # ⌘K / ↵ / esc display
│       │   ├── status-dot.svelte     # colored circle (ember/graphite/signal/green)
│       │   ├── divider.svelte
│       │   ├── card.svelte
│       │   ├── pin-marker.svelte     # map pin used in places-map widget and elsewhere
│       │   ├── avatar.svelte
│       │   ├── empty-state.svelte
│       │   ├── spinner.svelte
│       │   └── index.ts
│       ├── stores/                   # Svelte 5 runes stores
│       │   ├── user.state.svelte.ts
│       │   ├── palette.state.svelte.ts
│       │   ├── sync.state.svelte.ts  # last-sync timestamps per source
│       │   └── pinned.state.svelte.ts
│       ├── utils/
│       │   ├── cn.ts                 # CVA + tailwind-merge
│       │   ├── date.ts               # format date, relative time
│       │   ├── fuzzy.ts              # command palette fuzzy ranker
│       │   └── index.ts
│       ├── chrome/
│       │   ├── components/           # sidebar, breadcrumb, status-pip, spine-item
│       │   ├── state/                # chrome.state.svelte.ts (active spine, breadcrumbs)
│       │   ├── _stories/
│       │   ├── views/
│       │   │   └── app-shell.svelte  # used by root +layout
│       │   └── index.ts
│       ├── palette/
│       │   ├── components/           # palette-overlay, result-row, result-group, filter-tabs
│       │   ├── state/                # palette.state.svelte.ts, ranking.ts
│       │   ├── _stories/
│       │   ├── keyboard.ts           # ⌘K / Esc / arrows / ↵ bindings
│       │   └── index.ts
│       ├── widgets/
│       │   ├── components/           # widget-shell (eyebrow+footer chrome)
│       │   ├── kernel/               # widget-host.svelte (renders any tool payload)
│       │   ├── code-diff/            # per-widget folder w/ component + stories + mock
│       │   ├── workouts/
│       │   ├── places-map/           # uses leaflet + OSM tiles per memory
│       │   ├── weather/
│       │   ├── purchases/
│       │   ├── _stories/
│       │   └── index.ts
│       ├── today/
│       │   ├── components/           # hero-greeting, today-shape, focus-block, overnight-digest, open-threads, yesterday-summary, composer
│       │   ├── state/
│       │   ├── _stories/
│       │   ├── views/
│       │   │   └── today-view.svelte
│       │   └── index.ts
│       ├── threads/
│       │   ├── components/           # thread-list, thread-row, conversation, message, composer, tool-picker, source-chip
│       │   ├── state/                # threads.state.svelte.ts, composer.state.svelte.ts
│       │   ├── _stories/
│       │   ├── views/
│       │   │   ├── threads-view.svelte
│       │   │   └── thread-view.svelte
│       │   └── index.ts
│       ├── library/
│       │   ├── components/           # fields-grid, field-card, library-facet-nav
│       │   ├── _stories/
│       │   ├── views/
│       │   │   ├── library-index.svelte
│       │   │   └── fields-index.svelte
│       │   └── index.ts
│       ├── fields/                   # Field domain (generic + per-field)
│       │   ├── components/           # field-shell, field-hero, field-stats, sub-nav
│       │   ├── state/
│       │   ├── _stories/
│       │   ├── views/
│       │   │   └── field-detail.svelte
│       │   ├── health/               # per-field specialisation
│       │   │   ├── components/       # workout-card, weekly-grid, readiness-card, pr-list
│       │   │   ├── state/
│       │   │   ├── _stories/
│       │   │   └── views/
│       │   │       └── health-workouts.svelte
│       │   └── index.ts
│       └── agents/
│           ├── components/           # agents-list, agent-row, run-header, run-timeline, run-step, run-artifact
│           ├── state/
│           ├── _stories/
│           ├── views/
│           │   ├── agents-list.svelte
│           │   └── run-detail.svelte
│           └── index.ts
├── tests/
│   └── e2e/                          # Playwright specs — run ON THE BOX via CI, not locally
├── package.json
├── svelte.config.js
├── vite.config.ts
├── tsconfig.json
└── postcss.config.js
```

---

## Phases

Each phase is independently shippable. Stories and schemas land alongside every component — no "we'll add stories later."

### Phase 0 — Supersede existing scaffold

The current `ui/` directory has the old IA. Before adding the new structure, retire what doesn't fit.

- [ ] Move `ui/src/lib/api.ts` → `ui/src/lib/api/client.ts`, wrap into barrel (`api/index.ts`). Keep `api.test.ts` co-located.
- [ ] Delete `ui/src/routes/chat/`, `ui/src/routes/schedule/`, `ui/src/routes/settings/`, `ui/src/routes/tasks/` (old IA — superseded).
- [ ] Delete `ui/src/lib/components/` contents (old flat components — will be rebuilt domain-organised).
- [ ] Keep `ui/src/lib/theme/`, `utils.ts`, `types.ts` — refactor in later phases.
- [ ] Add a single root route `+page.svelte` that redirects to `/today` so the app isn't empty during early phases.

### Phase 1 — Foundations

- [ ] Install dependencies: `storybook@^8`, `@storybook/sveltekit`, `phosphor-svelte`, `zod`, `@faker-js/faker`, `cva`, `tailwind-merge`, `bits-ui`. Dev deps: `@storybook/addon-essentials`, `@storybook/addon-a11y`, `@playwright/test`.
- [ ] Initialise Storybook: `pnpm dlx storybook@latest init --type sveltekit`. Configure `.storybook/main.ts` to glob `src/lib/**/*.stories.ts`.
- [ ] Create `src/lib/theme/tokens.ts` with palette (paper, bench, graphite, ink, ember, signal), font families, and radii, mirroring the Paper mood board.
- [ ] Configure `app.css` with Tailwind 4 theme extension using `tokens.ts`. Font-family utilities: `font-display` (Playfair), `font-body` (Inter), `font-mono` (JetBrains Mono).
- [ ] Create `src/lib/typography/` primitives: `Display`, `Heading`, `Body`, `Meta`, `Stat`, `Eyebrow`. Each with `.stories.ts`.
- [ ] Create `src/lib/components/` primitives: `Button`, `Chip`, `KeycapHint`, `StatusDot`, `Divider`, `Card`, `EmptyState`, `Spinner`, `Avatar`. Each with `.stories.ts`. Where a primitive has non-trivial interactive state (tooltip, dropdown-menu, dialog, tabs, popover, toggle, switch, select, scroll-area, separator-with-role), wrap the corresponding Bits UI primitive rather than hand-rolling — styled via `cva` + tokens so the wrapper reads as an Ardent Forge component.
- [ ] Create `src/lib/icons/index.ts` re-exporting `Sun`, `ChatCircle`, `Books`, `Robot`, plus the common ones used in widgets (`{ }` for code.diff, `♥` for health.workouts, map pin, etc.) with preset weight=regular.
- [ ] Create `src/lib/schemas/primitives.ts` (IsoDate, IsoDuration, Id, Slug, Money, Url). Document conventions.
- [ ] Create `src/lib/utils/cn.ts` (CVA + twMerge), `date.ts`, `fuzzy.ts` (stub — real impl in palette phase).
- [ ] **Verify:** `pnpm storybook` renders typography + component primitive stories. Paper background, fonts load correctly. Dark mode deferred to later phase.

### Phase 2 — Chrome + shell

- [ ] `src/lib/chrome/components/spine-item.svelte` with Phosphor icon, label, meta, active state. Stories: default / active / with-live-indicator / with-count.
- [ ] `src/lib/chrome/components/sidebar.svelte` composing brand, four spine items, pinned list, recent-threads list (optional, only rendered on Today), ⌘K affordance, sync status. Stories for each spine active state.
- [ ] `src/lib/chrome/components/breadcrumb-strip.svelte` — three variants (top-level/none, nested 2, deep 3+, thread). Stories cover all four.
- [ ] `src/lib/chrome/state/chrome.state.svelte.ts` — active spine derived from URL, breadcrumb trail from route params.
- [ ] `src/lib/chrome/views/app-shell.svelte` — composes sidebar + breadcrumb + slot content. Used by root `+layout.svelte`.
- [ ] `src/lib/stores/sync.state.svelte.ts` with mock source timestamps (Strava, Notebook, Linear, Calendar, GitHub) — drives the sync pip colour/age.
- [ ] `src/lib/stores/pinned.state.svelte.ts` — user-curated shortcuts. Starts with mock defaults (Health/Workouts, Redpanda/Core, Today's log).
- [ ] Wire `routes/+layout.svelte` to render `<AppShell>`. `routes/+page.svelte` redirects to `/today`.
- [ ] **Verify:** navigating to `/today`, `/threads`, `/library`, `/agents` renders empty shells with correct sidebar active state and breadcrumbs matching the Chrome spec artboard.

### Phase 3 — Palette (⌘K)

- [ ] `src/lib/palette/state/palette.state.svelte.ts` — open/close, query, selected index.
- [ ] `src/lib/palette/state/ranking.ts` — the 5-rule ranker (exact → recency → pinned → context boost → verb-detection for actions).
- [ ] `src/lib/utils/fuzzy.ts` real implementation (small fuzzy matcher; or dep on `fuse.js`).
- [ ] `src/lib/palette/components/palette-overlay.svelte` — built on **Bits UI `Command`** (provides fuzzy filter primitive, keyboard nav, aria state); scrim + centered card + glass blur are the styling layer.
- [ ] `src/lib/palette/components/filter-tabs.svelte` — all / notes / threads / tasks / agents / actions. Built on Bits UI `Tabs`.
- [ ] `src/lib/palette/components/result-row.svelte` — icon (by result class) + title + breadcrumb subtitle + active-selection highlight. Rendered as `Command.Item`.
- [ ] `src/lib/palette/components/result-group.svelte` — `Command.Group` with section header.
- [ ] `src/lib/palette/keyboard.ts` — ⌘K global toggle (Bits Command handles Esc/↑/↓/↵ internally); we only add ⌘↵ open-in-new-thread.
- [ ] Seed with mocked index from `mocks/` (workouts, notes, threads, tasks, agents, hard-coded action verbs).
- [ ] Mount overlay in `app-shell.svelte`.
- [ ] **Verify:** ⌘K opens palette from any route; typing "today's workout" produces results matching the palette artboard (`2BB-0`).

### Phase 4 — Widget kernel + first widget

- [ ] `src/lib/schemas/widgets/code-diff.ts` — define the `CodeDiffPayload` zod schema (tool id, query context, file list w/ hunks, branch, stats, actions).
- [ ] `src/lib/mocks/widgets/code-diff.ts` — factory taking partial overrides.
- [ ] `src/lib/widgets/components/widget-shell.svelte` — eyebrow + tool badge + header meta slot + body slot + footer actions slot. This is the shared chrome.
- [ ] `src/lib/widgets/code-diff/code-diff.svelte` — wraps `widget-shell` with body-specific rendering (file rows, hunk lines, +/− gutter).
- [ ] `src/lib/widgets/kernel/widget-host.svelte` — discriminated switch on `tool` id → renders the matching widget component.
- [ ] Stories: `widget-shell.stories.ts` (empty shell), `code-diff.stories.ts` (default / no-hunks / many-files / conflict).
- [ ] **Verify:** code-diff story matches the Chat Widgets library artboard (`21O-0`).

### Phase 5 — Today

- [ ] `src/lib/schemas/thread.ts`, `schemas/task.ts`, `schemas/agent.ts` — enough to fuel Today's digest panels.
- [ ] `src/lib/mocks/` factories for each.
- [ ] `src/lib/today/components/` — hero-greeting, weather-strip-stat, tasks-due-stat, agent-runs-stat, today-shape (schedule timeline), focus-block (workout hero + tasks list), composer, overnight-digest, open-threads, yesterday-summary. Stories for each.
- [ ] `src/lib/today/views/today-view.svelte` composes everything.
- [ ] Wire `routes/today/+page.svelte`.
- [ ] **Verify:** Today matches the Paper artboard (`2BB-0`).

### Phase 6 — Threads

- [ ] `src/lib/schemas/thread.ts` extended — messages (user/assistant), tool-call payloads that embed widget schemas.
- [ ] `src/lib/threads/components/` — thread-list-panel, thread-row, conversation, user-message, assistant-message (embeds `<WidgetHost>` for tool results), composer (with scope chips `@thread`/`@today`/`/tools`, model indicator, ⌘↵ hint), tool-picker (Bits UI `Popover` + `Command` for searchable tool list).
- [ ] `src/lib/threads/state/composer.state.svelte.ts`.
- [ ] `src/lib/threads/views/threads-view.svelte` (list-only), `thread-view.svelte` (three-column: shell sidebar via layout, list panel, conversation).
- [ ] Route-level split: `/threads` → list; `/threads/[id]` → detail. Detail view re-uses list panel as middle column.
- [ ] **Verify:** thread view with three widgets stacked (weather + purchases + places-map) matches artboard `2SN-0`.

### Phase 7 — Library + Fields

- [ ] `src/lib/schemas/field.ts` — field metadata, counts, sources, status.
- [ ] `src/lib/mocks/field.ts` — seed with the seven fields from the Paper library artboard.
- [ ] `src/lib/library/components/fields-grid.svelte`, `field-card.svelte` (with sources + status chip + headline stats). Stories.
- [ ] `src/lib/library/views/fields-index.svelte`.
- [ ] `src/lib/fields/components/field-shell.svelte` — generic field detail template (hero + sub-nav + content slot).
- [ ] `src/lib/fields/health/` — `workout-card`, `weekly-grid`, `readiness-card`, `pr-list`, etc. `health-workouts.svelte` view matches artboard `1O7-0`.
- [ ] Routes: `/library/fields` (index), `/library/fields/[slug]` (generic — routes the health slug into the health view specifically; others get a generic placeholder until their domain exists).
- [ ] **Verify:** Library index + Health/Workouts pages match artboards `2ZV-0` and `1O7-0`.

### Phase 8 — Agents

- [ ] `src/lib/schemas/agent.ts` — agent type, run type (steps, status, meta, artifact reference).
- [ ] `src/lib/mocks/agent.ts` — the six agents from artboard `360-0`.
- [ ] `src/lib/agents/components/` — agents-list, agent-row (status chip, last activity, summary), run-header, run-meta-strip, run-timeline, run-step, run-artifact (embeds `<WidgetHost>` for the PR).
- [ ] Routes: `/agents`, `/agents/[agent]/[run]`.
- [ ] **Verify:** matches artboard `360-0`.

### Phase 9 — Remaining widgets

For each of `workouts`, `places-map`, `weather`, `purchases`:

- [ ] Schema in `schemas/widgets/`.
- [ ] Mock factory in `mocks/widgets/`.
- [ ] Component in `widgets/<name>/`.
- [ ] Stories covering default, edge-cases, and in-thread composition.
- [ ] Register in `widget-host.svelte`'s discriminator.

**Places-map specific:** install `leaflet` + types, render OSM tiles per `memory/project_map_widget_osm.md`. Map pins reuse `src/lib/components/pin-marker.svelte`. Nominatim for geocoding; throttle + cache.

### Phase 10 — Polish

- [ ] Dark mode: derive dark-palette tokens in `theme/tokens.ts`, use CSS custom properties with `prefers-color-scheme` + manual toggle in theme-store. Update component stories with dark-mode variants.
- [ ] Accessibility pass: keyboard nav for palette, focus traps, aria on chat composer, semantic headings per page.
- [ ] Visual regression: Chromatic on Storybook (or Playwright snapshot suite checked into repo).
- [ ] `src/lib/schemas/` — export a JSON-schema snapshot for each widget payload so the backend can validate emitted tool results against the same contract.
- [ ] Hybrid-mode env config: `VITE_API_URL` read in `api/client.ts`, with localhost fallback docs in README.
- [ ] E2E smoke suite (`tests/e2e/`) — runs against the deployed box, not locally. Covers: palette opens → fuzzy → navigates; thread composer round-trips; agent run detail loads.

---

## Conventions

**Svelte 5 runes only.** No `export let`, no `$:`, no `on:click`. `$state`, `$derived`, `$props`, `$effect`, `onclick`, `{#snippet}` / `{@render}` throughout.

**Stories co-locate with components.** Every `.svelte` gets a sibling `.stories.ts` in the same folder. Wrapper story helpers and shared mock data live in `_stories/`.

**Mocks never hand-crafted.** If a story needs data, it gets it from `src/lib/mocks/`. If the factory doesn't exist yet, add it — don't inline a literal object.

**Typography is imported, not inlined.** Use `<Display>`, `<Heading>`, `<Body>`, `<Meta>`, `<Stat>`, `<Eyebrow>` from `lib/typography`. This enforces the Playfair-for-words / Mono-for-numbers rule automatically.

**Numbers always mono.** Enforced by `<Stat>` wrapping every numeric value. Do not write raw numbers in Playfair or Inter contexts — wrap them in `<Stat>`.

**Domain isolation.** A component in `lib/today/` may not import from `lib/threads/`. If two domains need the same thing, it moves to `lib/components/` (UI) or `lib/<cross-cutting>/` (logic).

**Bits UI for complex, stateful primitives.** Any component whose correctness depends on focus management, keyboard behaviour, ARIA state, or portal/overlay logic must be built on Bits UI, not hand-rolled. Specifically: dialog, popover, dropdown menu, context menu, combobox, command (palette), tooltip, tabs, accordion, switch, toggle, select, date picker, scroll area, separator-with-role. Wrap the Bits primitive in a thin project-styled component in `src/lib/components/` — never import Bits directly from domain code. Style via `cva` + tokens so the wrapper still reads as an Ardent Forge component.

Use plain Svelte (no Bits) for: static layout, purely decorative chrome (chips, status dots, cards, dividers), and one-off visual compositions where there's no interactive state to manage. If you find yourself re-implementing focus traps, roving tabindex, or `aria-expanded` coordination — stop and wrap Bits instead.

The ⌘K palette specifically uses Bits UI's `Command` primitive as its foundation (fuzzy filtering + keyboard nav is non-trivial and battle-tested there).

**File naming.** kebab-case for files (`thread-list.svelte`), PascalCase for Svelte component exports. State files end `*.state.svelte.ts`. Stories end `*.stories.ts`. Tests end `*.test.ts`.

**Tests co-locate.** `inbox-submission-status.test.ts` next to `inbox-submission-status.ts`. E2E lives in `tests/e2e/` and runs on the box.

---

## Deliverable checklist (end-state)

- Four temporal-spine routes rendering correctly with chrome that matches the chrome spec artboard
- ⌘K palette invokable from any route with fuzzy results across all mocked indices
- Five production widgets implemented (code-diff, workouts, places-map, weather, purchases) with schemas + mocks + stories
- Library Fields index + Health/Workouts field detail matching Paper artboards
- Agents list + run detail with timeline and artifact embedding
- Every component has a story; every story uses schema-derived mocks
- `pnpm storybook` runs end-to-end offline; `pnpm dev` with `VITE_API_URL` set over Tailscale hits the real box
- Dark mode wired; a11y audited; visual regression in CI
