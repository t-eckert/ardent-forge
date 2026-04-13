# Ardent Forge — Design Spec

## Overview

Ardent Forge is an agentic development and life-coordination system running on a NixOS Bee Link mini PC (16GB RAM, 1TB storage, Intel CPU, no GPU). It operates as a monolithic Python (FastAPI) service with a SvelteKit web UI, accessible exclusively over Tailscale.

It has two modes of operation:

1. **Autonomous mode**: Polls Linear for labeled issues across all personal repos, picks them up, implements them in isolated git worktrees using Claude Code CLI, and creates PRs.
2. **Interactive mode**: A web UI where the user can chat with the system, dispatch ad-hoc tasks, monitor agent activity, and review results.

The system is task-type agnostic. Development is the first and primary capability, but the architecture supports any kind of task handler — financial reports, notebook updates, error triage, deep research, etc.

Ardent Forge is one of its own managed repos. It can pick up Linear issues for itself and submit PRs for its own improvement, subject to safety guardrails.

## NixOS Foundation

The Bee Link runs NixOS with a declarative configuration defining the entire system.

### System packages
- Python 3.12+
- Git
- Claude Code CLI
- GitHub CLI (`gh`)
- Ollama
- 1Password CLI (`op`)

### systemd services
- `ardent-forge` — main application
- `ollama` — local small model serving
- `postgresql` — for Grafana and services needing relational storage
- `redis` — caching, ephemeral state
- `grafana` — dashboards
- `prometheus` — metrics collection

### Developer environment
- The Bee Link doubles as an SSH-accessible dev box
- NixOS config based on the user's dotfiles repo (`~/Repos/github.com/t-eckert/dotfiles/`) so all personal tools (Neovim, Ghostty, Go, etc.) are present
- SSH access over Tailscale for manual coding sessions

### Networking
- Tailscale enabled, configured for the user's tailnet
- Firewall: only Tailscale interface exposed
- Static local IP (10.0.0.67)
- No public-facing services

### Secrets
- 1Password vault "Ardent Forge" holds all API keys and tokens
- systemd `ExecStartPre` uses `op run` to inject secrets as environment variables
- No secrets in Nix config or on disk in plaintext
- Secret references use 1Password URIs (e.g., `op://ArdentForge/anthropic-api-key/credential`)

### Required secrets
- Anthropic API key
- GitHub PAT
- Linear API key
- YNAB API token (future)
- Sentry auth token (future)

## Repository Structure

```
ardent-forge/
├── nix/                    # NixOS configuration
│   ├── flake.nix           # System flake
│   ├── configuration.nix   # Main system config
│   ├── services/           # Per-service NixOS modules
│   └── hardware.nix        # Bee Link hardware config
├── forge/                  # Python application
│   ├── api/                # FastAPI routes
│   ├── agents/             # Agent logic, dispatching
│   ├── tasks/              # Task queue, Linear sync
│   ├── models/             # SQLite models, state management
│   └── main.py             # Entry point
├── ui/                     # SvelteKit frontend
├── docs/                   # Design docs, specs
└── CLAUDE.md               # Agent instructions for this repo
```

## Agent Architecture

### The Forge (Coordinator)

The coordinator is task-type agnostic. It manages a queue of tasks, each with a type that determines which handler processes it.

**Responsibilities:**
1. Ingest tasks from any source (Linear polling, web UI chat, scheduled jobs, webhooks)
2. Route to the right handler based on task type (local model triage for ambiguous ones)
3. Manage concurrency (default: 2 parallel tasks max, configurable — constrained by 16GB RAM)
4. Persist state to SQLite on every state transition
5. Report status back to the source (Linear comment, web UI update, notification)

### Task Handlers

Handlers implement a common protocol:

```python
class TaskHandler:
    task_type: str              # "code", "research", "report", "notebook", "triage"
    async def triage(task)      # Can I handle this? What do I need?
    async def execute(task)     # Do the work
    async def verify(task)      # Did it work?
    async def deliver(task)     # PR, message, file, notification, etc.
```

### Initial handlers

| Handler | Trigger | Execution | Delivery |
|---------|---------|-----------|----------|
| **Code** | Linear issue labeled `ardent-forge` | Claude Code CLI in worktree | GitHub PR |
| **Research** | Linear issue or chat request | Claude with web search, Notebook context | Written report (Notebook or Linear comment) |
| **Report** | Scheduled (cron-like) | API calls (YNAB, etc.) + Claude for synthesis | Notebook entry, notification |
| **Notebook** | Scheduled or triggered | API calls (weather, etc.) + file writes | Commit to Notebook repo |
| **Triage** | Webhook or polling (Sentry, etc.) | Analyze error, then spawn a Code task | Linear issue + optional auto-fix PR |

### Code Handler Pipeline (detailed)

1. **Triage** — Local model (Ollama) classifies the issue: code task, research, or needs-human-input
2. **Analysis** — Optional. Claude Sonnet explores the target repo's codebase to build context
3. **Implementation** — Claude Code CLI runs in an isolated git worktree of the target repo, with that repo's CLAUDE.md as instructions
4. **Verification** — Runs the repo's build/test/lint commands (detected from CLAUDE.md, Taskfile, package.json, Cargo.toml, etc.)
5. **Self-Review** — Claude reviews the diff against the original issue
6. **Retry** — Up to 2 retries on failure, with accumulated error context
7. **PR Creation** — Creates a PR with verification status, review notes, and a link back to the Linear issue

### Task State Machine

States: `queued → triaging → executing → verifying → delivering → completed | failed`

Every state transition is persisted to SQLite immediately. Log buffering flushes every few seconds as a safety net.

### Scheduled Tasks

A cron table in SQLite. Configured through the web UI. Example: "Every Monday at 9am, run the YNAB report handler."

## Web UI

SvelteKit app served on the Bee Link, accessible over Tailscale. No auth layer — Tailscale is the perimeter.

### Pages

- **Dashboard** — Active tasks, recent completions/failures, upcoming scheduled tasks, agent health metrics
- **Chat** — Conversational interface to Ardent Forge. Send ad-hoc requests, ask questions. Backed by Claude Sonnet (default, configurable to Opus for complex requests). Each chat session maintains its own message context. Chat history persisted to SQLite.
- **Tasks** — List/detail view of all tasks. Filter by type, repo, status. Drill into execution logs, diffs, delivery artifacts.
- **Schedule** — Manage recurring tasks. Add/edit/remove cron-style schedules.
- **Settings** — Handler settings, Linear sync interval, model preferences, repo configuration.

### Tech stack
- SvelteKit 2, Svelte 5, TypeScript
- Tailwind CSS 4 with dark mode
- REST API + WebSockets (chat streaming, live task updates)
- Single-user, no multi-user support

## Data Model

SQLite database at `/var/lib/ardent-forge/forge.db`.

### tasks
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (ULID) | Primary key |
| type | TEXT | "code", "research", "report", "notebook", "triage" |
| status | TEXT | "queued", "triaging", "executing", "verifying", "delivering", "completed", "failed" |
| source | TEXT | "linear", "chat", "schedule", "webhook" |
| source_id | TEXT (nullable) | Linear issue ID, Sentry event ID, etc. |
| repo | TEXT (nullable) | Target repo for code tasks |
| title | TEXT | Task title |
| description | TEXT | Task description |
| handler_data | JSON | Handler-specific state, accumulated context, retry info |
| result | JSON (nullable) | Delivery artifacts: PR URL, report path, etc. |
| retries | INTEGER | Retry count |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |
| completed_at | TIMESTAMP (nullable) | |

### task_logs
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (ULID) | Primary key |
| task_id | TEXT (FK) | References tasks.id |
| timestamp | TIMESTAMP | |
| level | TEXT | "info", "error", "debug" |
| message | TEXT | |

### chat_messages
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (ULID) | Primary key |
| role | TEXT | "user", "assistant" |
| content | TEXT | |
| task_id | TEXT (nullable) | If this message spawned a task |
| created_at | TIMESTAMP | |

### schedules
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (ULID) | Primary key |
| name | TEXT | Human-readable name |
| cron_expr | TEXT | Cron expression |
| task_type | TEXT | Handler type to invoke |
| task_template | JSON | Pre-filled task fields |
| enabled | BOOLEAN | |
| last_run | TIMESTAMP (nullable) | |
| next_run | TIMESTAMP | |

### Persistence strategy
- State transitions write immediately via SQLite transactions
- Logs buffer briefly and flush every few seconds
- On startup, coordinator queries for non-terminal tasks and resumes them
- On graceful shutdown, in-progress tasks are set back to `queued` for retry
- Daily backup of SQLite file (scheduled task — the system backs itself up)

## Integrations

### 1Password
- All secrets in dedicated vault
- `op run` injects secrets as env vars on service start
- No plaintext secrets on disk

### Linear
- Polls GraphQL API on configurable interval (default: 5 minutes)
- Finds unassigned issues labeled `ardent-forge`
- Updates issue status as work progresses
- Posts comments with execution summaries, PR links, failure reports
- Task type inferred from Linear labels or triaged by local model

### GitHub
- GitHub CLI (`gh`) for PR creation
- Repos cloned/fetched into managed workspace (`/var/lib/ardent-forge/repos/`)
- Worktrees per task for isolation
- All access via GitHub PAT from 1Password

### Ollama (local models)
- Separate systemd service
- Called over localhost HTTP
- Used for task triage/classification, simple extraction, routing
- Model: small and fast (e.g., phi-3, qwen2)

### Future integrations (not v1)
- YNAB API for financial reports
- Weather API for notebook entries
- Sentry webhooks for error triage
- Notebook repo for knowledge retrieval

## Self-Building & Development Workflow

### Bootstrap
The initial implementation is manual. Once the code handler works, Ardent Forge can contribute to its own development.

### Self-building workflow
1. User creates Linear issues for Ardent Forge features/bugs
2. Coordinator picks them up like any other repo
3. Clones/worktrees its own repo, implements the change, runs tests
4. Creates a PR for user review
5. User merges, restarts the service with new code

### Safety guardrails
- **Cannot merge its own PRs** (hard rule)
- **Cannot modify `nix/` directory** (infrastructure changes need user review and manual apply)
- **Cannot modify guardrails module** (safety-critical code)
- **Cannot modify its own CLAUDE.md** without flagging
- **Cannot change secrets references or 1Password configuration**
- All self-modifications go through the same PR review as any other repo

### Testing requirements
- Unit tests for handler logic, state machine, task queue
- Integration tests for the full pipeline (issue → triage → execute → verify → PR)
- Verification must pass before a PR is created
- CI runs on GitHub Actions (not on the Bee Link) — a bad self-modification can't take down test infrastructure

### Deployment
- Initial: manual pull and restart
- Future: deploy handler that pulls latest merged code and restarts with rollback on health check failure

## Monitoring

Grafana and Prometheus run on the Bee Link to monitor the system itself:

- Task throughput, success/failure rates
- Agent execution times
- System resources (CPU, memory, disk)
- Ollama inference latency
- Linear/GitHub API health
- SQLite database size

## Out of Scope (v1)

- Migration of existing homelab services to Cloudflare/Fly (separate effort)
- Multi-user support
- Public-facing services
- GPU/large local model serving
- Auto-deployment of self-modifications (manual restart for now)
