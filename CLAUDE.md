# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Ardent Forge is a personal agentic platform centered around interactions with a personal Obsidian notebook. A leader agent coordinates specialized sub-agents for notebook-driven tasks: daily logs, weekly reviews, knowledge retrieval, and work automation. The notebook (`forge/notebook/`) and notebook-aware orchestrator are the strategic core. Python + TypeScript monorepo.

## Commands

```bash
# Backend (Python 3.13, uv)
uv run forge                          # Start server (port 7030)
uv run pytest -q                      # All tests
uv run pytest tests/test_api.py       # Single file
uv run pytest -k test_nudge           # Single test by name

# Frontend (Node 22, pnpm)
cd ui
pnpm dev                              # Dev server (port 5180)
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

Active agents: Echo (debug), Code (Claude Code in workspace repos), Plan (self-building), Research (Obsidian vault), Tickets (Linear sync).

**Connectors** (`forge/connectors/`) expose tools to agents. Agents declare which connectors they need via `connectors: list[str]`. The coordinator builds an `AgentContext` with resolved tools.

**Key modules:**
- `forge/coordinator.py` — core loop: polls for tasks, dequeues, orchestrates agent stages
- `forge/store.py` — TaskStore (task CRUD, SQLite)
- `forge/thread_store.py` — ThreadStore (conversations, messages with variant types)
- `forge/orchestrator/` — dispatches chat→task and posts result widgets back to threads
- `forge/api/` — REST endpoints (tasks, chat, threads, schedules, memory, agents, health)
- `forge/linear/` — Linear integration (poller, client, projects, sync)
- `forge/memory/` — markdown-based memory store
- `forge/notebook/` — Obsidian vault reader/writer
- `forge/claude.py` — Claude Code runner (spawns CLI subprocesses)
- `forge/metrics.py` — Prometheus metrics (`/metrics` endpoint)

### Frontend: `ui/`

SvelteKit 2 + Svelte 5 + Tailwind CSS 4 + TypeScript. Static adapter. Component library uses `bits-ui`, `phosphor-svelte` icons, `cva` for variants, `tailwind-merge`+`clsx` for class merging.

Routes: `tasks/`, `threads/`, `library/`, `today/`. Shared code in `ui/src/lib/`. Storybook for component development. Playwright E2E tests fall back to mock data when API is unreachable.

API proxy configured via `VITE_API_PROXY` env var (defaults to `http://localhost:7030`).

### Tests: `tests/`

pytest + pytest-asyncio with `asyncio_mode = "auto"`. In-memory SQLite for isolation. External HTTP mocked with `respx`. Fixtures in `tests/conftest.py` provide `db`, `store`, `registry`.

### Infrastructure: `nix/`

NixOS deployment with systemd services. Grafana dashboards in `grafana/dashboards/`.

### Design docs: `docs/superpowers/specs/`

Specs use YAML frontmatter (`---` delimited) — this is required for the spec watcher to detect them.

## Key Patterns

- **IDs**: Tasks and threads use ULIDs (sortable, `ulid-py`)
- **Models**: Pydantic v2 with `BaseModel`, `StrEnum` for status/type enums
- **Thread messages**: variant types (text, widget, task-dispatched, task-resolved)
- **Chat dispatch**: `forge/api/chat.py` uses a `dispatch_task` meta-tool so chat can create tasks linked to the originating thread
- **Self-building**: Plan agent clones the repo, modifies code, commits. Watchers in `forge/watchers/` coordinate spec→plan flow
