# Ardent Forge

Ardent Forge is a personal developer-toolbox control plane for a single NixOS box, accessed over Tailscale. It gives you agentic Claude sessions from chat, Linear issues, and cron schedules — with 1Password for secrets, GitHub for code, and Zellij for session visibility.

## Design Principles

- **The box is nukable.** No stateful pets. All repos clone fresh from GitHub; secrets resolve at runtime from 1Password.
- **Secrets from 1Password.** Decrypted values are never persisted to disk. The `op` CLI resolves `op://` references at task start. Each repo's `repo.yaml` declares which paths it needs; OPConnector enforces the allowlist.
- **Code from GitHub.** Claude Code clones repos into `~/Repos/<name>` and works in that directory. The workspace survives rebuilds.
- **Zellij for visibility.** Code tasks run inside a named Zellij session (`agent-<task-id>`) so you can attach and watch live. The session name and attach command are in the task result.
- **Tailscale for access.** The service binds on the Tailscale interface. Dev servers declared in `repo.yaml` are exposed via `tailscale serve --https=<port>` at startup.

## Architecture

### Backend: `forge/`

FastAPI + async SQLite (aiosqlite). All settings via `FORGE_` env vars — see `forge/config.py`.

**Task pipeline** — states declared in `forge/state.py`:
```
queued → triaging → executing → verifying → delivering → completed
                                                          ↑
failed ──────────────────────────── requeue ──────────────┘
```

**Agents** — stage-declared; each lists which pipeline stages it implements:
- **Echo** — debug agent, immediate round-trip
- **Code** — Claude Code in a Zellij session; resolves 1Password env, clones repo, runs `claude --dangerously-skip-permissions`
- **Plan** — self-building; reads a spec, writes a plan, commits it
- **Tickets** — syncs Linear issue state

**Connectors** — registered at startup, provide tools to agents and chat:
- **OPConnector** — resolves `op://` references; no chat tools (secret-store only)
- **GitHubConnector** — PR creation, repo reads
- **WebSearchConnector** — Tavily web search (optional)
- **NotebookConnector** — read-only Obsidian vault access (optional, if vault is present)
- **SpeedtestConnector** — periodic bandwidth measurements, watcher

**Coordinator** — polls task queue, orchestrates agent stages, fires cron schedules, polls Linear, posts PR links back to Linear issues after delivery.

**Key modules:**
- `forge/coordinator.py` — core loop: linear poll → cron fire → dequeue → agent stages
- `forge/store.py` — TaskStore: task CRUD + schedule CRUD
- `forge/thread_store.py` — ThreadStore: conversations, messages with variant types
- `forge/orchestrator/` — ForgeOrchestrator: system prompt assembly, tool dispatch, resolution posting
- `forge/repos/` — RepoRegistry: scans `~/Repos/*/` for git repos + `repo.yaml` configs
- `forge/zellij/` — ZellijRunner: runs Code tasks in named Zellij sessions
- `forge/tailscale/` — TailscaleServe: exposes dev ports via `tailscale serve --https`
- `forge/linear/` — LinearPoller + LinearClient: ingests `ardent-forge` label issues, dispatches `claude`-labeled issues as Code tasks
- `forge/api/schedules.py` — cron schedules CRUD; coordinator fires due schedules each tick
- `forge/memory/` — markdown-based memory store for the chat persona
- `forge/claude.py` — ClaudeRunner: spawns `claude` CLI subprocesses (fallback path)
- `forge/metrics.py` — Prometheus metrics at `/metrics`

### Frontend: `ui/`

SvelteKit 2 + Svelte 5 + Tailwind CSS 4 + TypeScript. Static adapter. `bits-ui`, `phosphor-svelte` icons, `cva` + `tailwind-merge`.

Routes:
- `/` (today) — Dashboard: active tasks, queued tasks, repo list, open threads
- `/threads/` — chat threads with Forge
- `/tasks/` — task list and detail
- `/library/` — agents, connectors, memory, repos, schedules, log

API proxy via `VITE_API_PROXY` (defaults to `http://localhost:7030`).

### Repo Configuration: `repo.yaml`

Each repo can have a `repo.yaml` at its root:

```yaml
dev_port: 5173           # exposed via tailscale serve --https=5173
claude_label: my-label   # Linear label that triggers Code tasks for this repo
env:
  STRIPE_KEY: op://Personal/Stripe/api_key   # resolved by OPConnector at task start
  DATABASE_URL: postgresql://localhost/myapp
cron_tasks:
  - name: nightly-lint
    cron: "0 2 * * *"
    prompt: "Fix all linting errors in the repo"
```

### Chat Dispatch

The chat persona is ForgeOrchestrator. When you ask Forge to do work against a repo, it calls the `dispatch_task` meta-tool, which creates a Task linked to the thread. The coordinator picks it up, runs the Code agent, and posts the result (PR link, Zellij session) back to the thread as a resolved card.

### Linear Integration

Forge polls Linear for issues labeled `ardent-forge`. Issues with an additional `claude` label are dispatched as Code tasks — the issue description should include `Repo: owner/name`. After delivery, Forge posts the PR URL as a comment on the Linear issue.

### Cron Schedules

Schedules are stored in SQLite (`/api/schedules`). Each schedule has a cron expression, a task type, and a template (repo, prompt, label). The coordinator fires due schedules each tick and advances `next_run` immediately to prevent double-fire.

## Infrastructure

NixOS + systemd services in `nix/`. The service runs as `ardent-forge.service` (managed by `sudo systemctl restart ardent-forge`). Grafana dashboards in `grafana/dashboards/`. Prometheus scrapes `/metrics`.

Workspace root: `~/Repos/` (configurable via `FORGE_WORKSPACE_DIR`).

## What This Is Not

- Not a Podman/container orchestrator. Claude Code runs directly on the box inside Zellij.
- Not notebook-centric. The Obsidian vault is available read-only if present, but it's not the point.
- Not multi-user. It's a personal tool for one engineer.
