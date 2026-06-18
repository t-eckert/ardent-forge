# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Ardent Forge is a personal developer-toolbox control plane for a single NixOS box accessed over Tailscale. It runs agentic Claude Code sessions (via Zellij) triggered from chat threads, Linear issues (`claude` label), and cron schedules. Secrets come from 1Password; code comes from GitHub. Python + TypeScript monorepo.

## Commands

```bash
# Backend (Python 3.13, uv)
uv run forge                          # Start server (port 7030)
uv run pytest -q                      # All tests
uv run pytest tests/test_api.py       # Single file
uv run pytest -k test_nudge           # Single test by name
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
pnpm dev   # against the box: cp ui/.env.local.example ui/.env.local first (proxies /api over Tailscale)
pnpm build                            # Production build
pnpm check                            # Svelte typecheck
pnpm test                             # Unit + Storybook tests (needs chromium)
pnpm test:e2e                         # Playwright smoke tests
pnpm storybook                        # Storybook dev (port 6006)
```

CI runs backend and frontend in parallel on push to `main` and on PRs. Some tests create real git commits, so git identity must be configured (CI does this; locally it uses your global config). Backend CI also requires `ripgrep`.

## Architecture

### Backend: `forge/`

FastAPI + async SQLite (aiosqlite). Settings via env vars with `FORGE_` prefix (see `forge/config.py`).

**Task pipeline** — tasks flow through states declared in `forge/state.py`:
```
queued → triaging → executing → verifying → delivering → completed
                                                          ↑
failed ──────────────────────────── requeue ──────────────┘
```

**Agents** (`forge/agents/`) are stage-declared: each agent lists which pipeline stages it implements (`stages = ["triage", "execute", "verify"]`). The coordinator (`forge/coordinator.py`) skips undeclared stages. `execute` is required; `triage`/`verify` are gates (return bool); `execute`/`deliver` are producers (return dict merged into task result).

Active agents: Echo (debug), Code (Claude Code via Zellij in workspace repos), Plan (self-building), Tickets (Linear sync).

**Connectors** (`forge/connectors/`) expose tools to agents and chat. Agents declare which connectors they need via `connectors: list[str]`. The coordinator builds an `AgentContext` with resolved tools.

Active connectors: OPConnector (1Password secret resolution), WebSearchConnector (Tavily, optional), NotebookConnector (read-only Obsidian vault, optional), SpeedtestConnector (periodic bandwidth watcher).

**Key modules:**
- `forge/coordinator.py` — core loop: Linear poll → cron fire → dequeue → orchestrate agent stages → post results
- `forge/store.py` — TaskStore (task CRUD + schedule CRUD, SQLite)
- `forge/thread_store.py` — ThreadStore (conversations, messages with variant types)
- `forge/orchestrator/` — ForgeOrchestrator: system prompt assembly, tool schemas, chat→task dispatch, resolution posting
- `forge/api/` — REST endpoints (tasks, chat, threads, schedules, memory, agents, repos, notebook, health)
- `forge/repos/` — RepoRegistry: scans `~/Repos/*/` for git repos + `repo.yaml` config (dev_port, env, claude_label)
- `forge/zellij/` — ZellijRunner: runs Code tasks in named Zellij sessions (`agent-<task-id>`)
- `forge/tailscale/` — TailscaleServe: exposes repo dev_ports via `tailscale serve --https`
- `forge/linear/` — LinearPoller + LinearClient: ingests `ardent-forge` label issues; `claude` label → Code task; posts PR link on delivery
- `forge/connectors/onepassword.py` — OPConnector: resolves `op://` references via `op read`; enforces `allowed_op_paths` from repo.yaml
- `forge/memory/` — markdown-based memory store
- `forge/notebook/` — Obsidian vault reader (read-only)
- `forge/claude.py` — ClaudeRunner (spawns CLI subprocesses; fallback path when Zellij unavailable)
- `forge/metrics.py` — Prometheus metrics (`/metrics` endpoint)
- `forge/mcp/` — FastMCP server mounted at `/mcp`; exposes Forge's tasks, memory, repos, schedules, and (when configured) notebook + web search to local Claude Code sessions. Tools wrap existing services, injected via `configure()` in `main.py`'s lifespan.

### Frontend: `ui/`

SvelteKit 2 + Svelte 5 + Tailwind CSS 4 + TypeScript. Static adapter. Component library uses `bits-ui`, `phosphor-svelte` icons, `cva` for variants, `tailwind-merge`+`clsx` for class merging.

Routes: `today/` (Dashboard), `threads/`, `tasks/`, `library/` (agents, connectors, memory, repos, schedules, log). Shared code in `ui/src/lib/`. Storybook for component development. Playwright E2E tests fall back to mock data when API is unreachable.

API proxy configured via `VITE_API_PROXY` env var (defaults to `http://localhost:7030`). For hybrid dev — running the UI on another machine (e.g. a Mac, for design tools like Paper) against the live Forge on the box — copy `ui/.env.local.example` to `ui/.env.local`; `vite.config.ts` resolves the target via `loadEnv`, so plain `pnpm dev` then proxies `/api` and `/health` to the box over Tailscale. An inline `VITE_API_PROXY=... pnpm dev` still overrides the file.

### Tests: `tests/`

pytest + pytest-asyncio with `asyncio_mode = "auto"`. In-memory SQLite for isolation. External HTTP mocked with `respx`. Fixtures in `tests/conftest.py` provide `db`, `store`, `registry`.

### Infrastructure: `nix/`

NixOS deployment with systemd services. `sudo systemctl restart ardent-forge` to apply. Grafana dashboards in `grafana/dashboards/`.

Workspace root: `~/Repos/` (env var `FORGE_WORKSPACE_DIR`).

### Design docs: `docs/superpowers/specs/`

Specs use YAML frontmatter (`---` delimited) — this is required for the spec watcher to detect them.

## Key Patterns

- **IDs**: Tasks and threads use ULIDs (sortable, `ulid-py`)
- **Models**: Pydantic v2 with `BaseModel`, `StrEnum` for status/type enums
- **Thread messages**: variant types (text, widget, task-dispatched, task-resolved)
- **Chat dispatch**: `forge/api/chat.py` uses a `dispatch_task` meta-tool so chat can create tasks linked to the originating thread; `repo` field passes the target GitHub repo
- **Secrets**: never persisted; OPConnector resolves `op://` refs at task start using the per-repo `allowed_op_paths` allowlist from `repo.yaml`
- **Zellij sessions**: Code agent creates a named Zellij session; result includes `zellij_session` and `attach_cmd` for live observation
- **Cron schedules**: stored in SQLite; coordinator fires due schedules each tick, advances `next_run` immediately to prevent double-fire
- **Linear dispatch**: `claude` label on a Linear issue → Code task; `Repo: owner/name` in description sets the repo; PR link posted back as comment after delivery
- **Self-building**: Plan agent clones the repo, modifies code, commits. SpecWatcher in `forge/watchers/` coordinates spec→plan flow
