# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Ardent Forge is a personal developer-toolbox control plane for a single NixOS box accessed over Tailscale. It runs agentic Claude Code sessions (via Zellij) dispatched from the UI, the MCP server, Linear issues (`claude` label), and cron schedules. Secrets come from 1Password; code comes from GitHub. Python + TypeScript monorepo.

## Commands

```bash
# Backend (Python 3.13, uv)
uv run forge                          # Start server (port 7030)
uv run pytest -q                      # All tests
uv run pytest tests/test_api.py       # Single file
uv run pytest -k test_nudge           # Single test by name
uv run ruff check forge tests scripts # Lint
uv run ruff format forge tests scripts# Format (line-length 100)
```

```bash
# MCP server (exposed by the running backend at /mcp)
claude mcp add --transport http forge http://localhost:7030/mcp                       # on the box
claude mcp add --transport http forge https://ardent-forge.feist-gondola.ts.net/mcp   # from another tailnet device (via Caddy)
```

```bash
# Frontend (Node 22, pnpm)
cd ui
pnpm dev                              # Dev server (port 5180)
                                      # Hybrid (UI on another machine, API on the box over Tailscale):
                                      #   cp ui/.env.local.example ui/.env.local, then pnpm dev
pnpm build                            # Production build
pnpm check                            # Svelte typecheck
pnpm test                             # Unit + Storybook tests (needs chromium)
pnpm test:e2e                         # Playwright smoke tests
pnpm storybook                        # Storybook dev (port 6006)
```

There is no CI — run `uv run pytest -q`, `uv run ruff check`, and `pnpm check` before pushing. Pushing to `main` triggers autodeploy on the box (`nix/services/autodeploy.nix` polls every 5 min, then `nixos-rebuild switch` + service restart) with no test gate. Some tests create real git commits, so git identity must be configured. The notebook tests require `ripgrep`.

## Architecture

### Backend: `forge/`

FastAPI + async SQLite (aiosqlite). Settings via env vars with `FORGE_` prefix (see `forge/config.py`).

**Task pipeline** — tasks flow through states declared in `forge/state.py`:
```
queued → triaging → executing → verifying → delivering → completed
                        │            │           ↑
                        └────────────┴──→ awaiting_approval   (when require_approval;
                                                               approve → delivering,
failed ── requeue → queued                                     reject → cancelled)
```
Any active state can move to `failed` (retried with backoff up to `max_retries`, then terminal) or `cancelled`.

**Task dispatch** — four entry points, all landing in the same queue: `POST /api/tasks` from the UI (source `manual`, optional `require_approval`), the MCP `dispatch_task` tool, the Linear poller, and cron schedules. Dispatchers call `coordinator.nudge()` so processing starts within seconds instead of on the next poll tick.

**Steering** — `POST /api/tasks/{id}/retry|cancel|approve|reject|follow-up`. Follow-up creates a continuation task linked via `continues_task_id`; the Code agent resumes in the original worktree/session.

**Agents** (`forge/agents/`) are stage-declared: each agent lists which pipeline stages it implements (`stages = ["triage", "execute", "verify"]`). The coordinator (`forge/coordinator.py`) skips undeclared stages. `execute` is required; `triage`/`verify` are gates (return bool); `execute`/`deliver` are producers (return dict merged into task result).

Active agents: Echo (debug), Code (Claude Code via Zellij in workspace repos), Plan (self-building), Tickets (Linear sync).

**Connectors** (`forge/connectors/`) expose tools to agents. Agents declare which connectors they need via `connectors: list[str]`. The coordinator builds an `AgentContext` with resolved tools.

Active connectors: OPConnector (1Password secret resolution, no chat tools), WeatherConnector, WebSearchConnector (Tavily, optional), NotebookConnector (Obsidian vault, read **and write**, optional; needs `ripgrep`), SpeedtestConnector (bandwidth watcher, opt-in via `FORGE_SPEEDTEST_INTERVAL_MINUTES`).

**Key modules:**
- `forge/coordinator.py` — core loop: connector health → Linear poll → watchers → cron fire → dequeue → orchestrate agent stages; `nudge()` wakes it early
- `forge/store.py` — TaskStore (task CRUD + schedule CRUD, SQLite)
- `forge/api/` — REST endpoints (tasks + steering, schedules, memory, agents, connectors, repos, notebook, weather, uploads, health)
- `forge/repos/` — RepoRegistry: scans `~/Repos/*/` for git repos and `~/Projects/*/` for repo groups; can clone by URL
- `forge/zellij/` — ZellijRunner: runs Code tasks in named Zellij sessions (`agent-<task-id>`)
- `forge/git.py` — GitOps: agent work happens in `git worktree`s under `<repo>/.worktrees/`; `forge/worktree_reaper.py` reclaims stale ones after `worktree_ttl_hours`
- `forge/linear/` — LinearPoller + LinearClient: `claude` label → Code task; `Repo: owner/name` in description sets the repo; PR link posted back as comment after delivery
- `forge/connectors/onepassword.py` — OPConnector: resolves `op://` references via `op read` against an explicit allowlist; values never persisted
- `forge/verify.py` — post-execute verification: detects and runs the repo's test commands, records passed/failed/no_tests/inconclusive in the task result
- `forge/guardrails.py` — self-modification safety: agents working on this repo cannot touch `nix/`, `CLAUDE.md`, or `guardrails.py`; Plan/Tickets are further restricted to `docs/superpowers/`
- `forge/watchers/` — SpecWatcher (spec → plan task) and PlanMergeWatcher for the self-building flow
- `forge/memory/` — markdown-based memory store
- `forge/notebook/` — Obsidian vault reader + writer (ripgrep-backed search; daily-log drafting, week review, stalled-work tools surface through the connector)
- `forge/claude.py` — ClaudeRunner (spawns CLI subprocesses; fallback path when Zellij unavailable)
- `forge/metrics.py` — Prometheus metrics (`/metrics` endpoint)
- `forge/mcp/` — FastMCP server mounted at `/mcp`; exposes task dispatch/inspection, memory, repos, schedules, weather, and (when configured) notebook + web search to Claude Code sessions. Tools wrap existing services, injected via `configure()` in `main.py`'s lifespan.

### Frontend: `ui/`

SvelteKit 2 + Svelte 5 + Tailwind CSS 4 + TypeScript. Static adapter. Component library uses `bits-ui`, `phosphor-svelte` icons, `cva` for variants, `tailwind-merge`+`clsx` for class merging.

Routes: `today/` (dashboard), `tasks/` (list + `[id]` detail with steer controls: cancel/approve/reject/retry/follow-up, polling while active), `repos/`, `library/` (agents, connectors, memory, schedules, log), `settings/`. Shared code in `ui/src/lib/`; API responses are schema-validated (Zod) in `ui/src/lib/schemas`. Storybook for component development; story `play` functions run as interaction tests under `pnpm test`. Playwright E2E smoke tests fall back to mock data when the API is unreachable — each test is annotated with its `api-mode`, and `E2E_REQUIRE_API=1` fails the run instead of falling back. Visual regression baselines are platform-suffixed; regenerate on the machine you compare on.

API proxy configured via `VITE_API_PROXY` env var (defaults to `http://localhost:7030`). For hybrid dev — running the UI on another machine (e.g. a Mac, for design tools like Paper) against the live Forge on the box — copy `ui/.env.local.example` to `ui/.env.local`; `vite.config.ts` resolves the target via `loadEnv`, so plain `pnpm dev` then proxies `/api` and `/health` to the box over Tailscale. An inline `VITE_API_PROXY=... pnpm dev` still overrides the file.

### Tests: `tests/`

pytest + pytest-asyncio with `asyncio_mode = "auto"`. In-memory SQLite for isolation. External HTTP mocked with `respx`. Fixtures in `tests/conftest.py` provide `db`, `store`, `registry`.

### Infrastructure: `nix/`

NixOS deployment with systemd services (`nix/services/`: forge itself, autodeploy, Caddy, monitoring, ntfy, notebook sync, and friends). `sudo systemctl restart ardent-forge` to apply a code change manually; autodeploy does the same on new `main` commits. Tailnet exposure is handled here (Caddy/tsnet), not in the backend. Grafana dashboards in `grafana/dashboards/`.

Workspace root: `~/Repos/` (env var `FORGE_WORKSPACE_DIR`).

### Design docs: `docs/superpowers/`

Specs live in `specs/`, dated implementation plans in `plans/`. Specs use YAML frontmatter (`---` delimited) — this is required for the spec watcher to detect them.

## Key Patterns

- **IDs**: Tasks use ULIDs (sortable, `ulid-py`)
- **Models**: Pydantic v2 with `BaseModel`, `StrEnum` for status/type enums
- **Approval gate**: tasks created with `require_approval` pause in `awaiting_approval` before delivery; approve/reject via API or task detail UI
- **Secrets**: never persisted; OPConnector resolves `op://` refs at task start against an explicit per-repo allowlist
- **Zellij sessions**: Code agent creates a named Zellij session; result includes `zellij_session` and `attach_cmd` for live observation
- **Worktrees**: agents never work on your checkout's branch — each task gets a `git worktree` in `<repo>/.worktrees/<branch>`, reaped after `worktree_ttl_hours`
- **Cron schedules**: stored in SQLite; coordinator fires due schedules each tick, advances `next_run` immediately to prevent double-fire
- **Linear dispatch**: `claude` label on a Linear issue → Code task; `Repo: owner/name` in description sets the repo; PR link posted back as comment after delivery
- **Self-building**: SpecWatcher turns new specs into Plan tasks; guardrails in `forge/guardrails.py` protect `nix/`, `CLAUDE.md`, and the guardrails themselves from agent modification
- **Timezone**: wall-clock date logic ("today" for notebook logs) derives from `FORGE_TIMEZONE`, not the server's UTC clock
