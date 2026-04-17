# Ardent Forge — Architecture

Ardent Forge is a personal agentic platform centered around an Obsidian notebook. A leader agent coordinates specialized sub-agents for notebook-driven tasks: daily logs, weekly reviews, knowledge retrieval, and work automation.

Python + TypeScript monorepo. FastAPI backend, SvelteKit frontend, SQLite persistence, NixOS deployment.

---

## System overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        SvelteKit UI                             │
│   /today  /threads  /tasks  /library  /settings                 │
│                         │                                       │
│                    API proxy (Vite)                              │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP
┌─────────────────────────▼───────────────────────────────────────┐
│                      FastAPI server                              │
│                                                                  │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │   Chat API   │  │   Orchestrator   │  │   Coordinator    │   │
│  │  (streaming) │──│ (prompt assembly │──│  (task pipeline) │   │
│  │              │  │  + tool routing) │  │                  │   │
│  └──────────────┘  └──────────────────┘  └──────┬───────────┘   │
│                                                  │               │
│  ┌──────────────────────────────────────────────▼────────────┐  │
│  │                    Agent Registry                          │  │
│  │  Echo · Code · Plan · Research · Studio · Tickets          │  │
│  └──────────────────────────┬─────────────────────────────────┘  │
│                              │                                    │
│  ┌──────────────────────────▼─────────────────────────────────┐  │
│  │                  Connector Registry                         │  │
│  │  Notebook (14 tools) · WebSearch · Weather · Workout ·     │  │
│  │  Studio · Speedtest                                         │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │  SQLite DB │  │  Memory    │  │  Notebook   │  │  Linear    │  │
│  │  (tasks,   │  │  Store     │  │  (Obsidian  │  │  Poller    │  │
│  │  threads)  │  │  (markdown)│  │   vault)    │  │            │  │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

---

## Backend

### Entry point

`uv run forge` invokes `forge.main:run()`. The FastAPI lifespan context manager:

1. Initializes the SQLite database and runs schema migrations
2. Instantiates `NotebookReader` and `NotebookWriter` (if vault directory exists)
3. Registers all connectors and calls `setup()` on each
4. Registers all agents
5. Creates the `ForgeOrchestrator` (prompt assembly, tool routing)
6. Starts the `Coordinator` loop as a background `asyncio.Task`
7. Starts external pollers (Linear) and watchers (spec, plan-merge)
8. Mounts the built SvelteKit app as a static SPA fallback

Server binds to `FORGE_HOST:FORGE_PORT` (default `0.0.0.0:7030`).

### Task pipeline

Tasks flow through a state machine declared in `forge/state.py`:

```
queued → triaging → executing → verifying → delivering → completed
                                                          ↑
failed ──────────────────────────── requeue ──────────────┘
```

The `transition(current, target)` function validates against `VALID_TRANSITIONS` and raises on illegal moves.

**Task model** (`forge/models.py`):
- `id` — ULID (sortable)
- `type` — maps to an agent (e.g., `code`, `research`, `plan`)
- `status` — `TaskStatus` enum
- `source` — `LINEAR | CHAT | SCHEDULE | WEBHOOK`
- `handler_data` — dict, agent-produced intermediate state between stages
- `result` — dict, final output after all stages complete

### Coordinator

`forge/coordinator.py` — the core loop.

- `run_loop(poll_interval)` — infinite loop calling `tick()`, sleeping between cycles unless nudged
- `tick()` — one cycle: poll Linear, run watchers, call `process_pending()`
- `process_pending()` — dequeue up to `max_concurrent` tasks

Per-task processing:
1. Look up agent by `task.type`
2. Build `AgentContext` with tools resolved from the agent's declared `connectors`
3. Execute declared stages in order: **triage** → **execute** → **verify** → **deliver**
4. Merge producer results (execute + deliver) into final `result`
5. `mark_completed(task_id, result)`
6. If an orchestrator is configured: `post_resolution(task, result)` posts a widget back to the origin thread

**Nudge mechanism**: When chat dispatches a task, it calls `coordinator.nudge()` which sets an `asyncio.Event`, waking the loop from its poll sleep for near-instant pickup.

### Agent system

Agents implement a protocol defined in `forge/agents/__init__.py`:

```python
class Agent(Protocol):
    name: str
    task_type: str
    stages: list[Stage]       # must include 'execute'
    connectors: list[str]     # connector names to request tools from

    async execute(task, ctx) -> dict    # required, producer
    async triage(task, ctx) -> bool     # optional, gate
    async verify(task, ctx) -> bool     # optional, gate
    async deliver(task, ctx) -> dict    # optional, producer
```

The coordinator skips stages an agent doesn't declare. Gate stages (triage, verify) return `bool` — `False` fails the task. Producer stages (execute, deliver) return `dict` merged into the result.

**Active agents:**

| Agent | Type | Stages | Connectors | Purpose |
|-------|------|--------|------------|---------|
| Echo | `echo` | execute | — | Debug; echoes task title |
| Code | `code` | triage, execute, verify, deliver | github | Clone repo → Claude Code → test → PR |
| Plan | `plan` | triage, execute, verify, deliver | github | Read spec → generate plan → PR |
| Research | `research` | triage, execute, verify, deliver | notebook, web_search | Run Claude Code in vault → create wiki/field entries |
| Studio | `studio` | triage, execute, verify, deliver | notebook | Art-study mentor anchored to syllabus |
| Tickets | `tickets` | triage, execute, verify, deliver | linear | Parse plan → create Linear project + issues |

### Connector system

Connectors expose tools to agents. Defined in `forge/connectors/__init__.py`:

```python
@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict        # JSON Schema for Claude
    execute: Callable         # async (params) -> dict
    connector_name: str
    long_running: bool        # if True, chat promotes to Task dispatch
    to_widget: Callable|None  # render result as thread widget
```

The `ConnectorRegistry` resolves tools by connector name. Agents declare which connectors they need; the coordinator builds a scoped `AgentContext` with only the relevant tools.

**Registered connectors:**

| Connector | Tools | Notes |
|-----------|-------|-------|
| Notebook | 14 tools | search, read, write, append, list, resolve_wikilink, recent, log, draft_log, week_review, stalled_work, summarize_log |
| WebSearch | 1 | Tavily-backed web search |
| Weather | 1 | get_weather |
| Workout | ~3 | Strava + notebook workout logs |
| Studio | ~2 | Art syllabus context |
| Speedtest | 1 | Bandwidth measurement |

### Orchestrator

`forge/orchestrator/` bridges chat and the task pipeline.

**System prompt assembly** (5 layers):
1. **Persona** — static identity and principles
2. **Memory** — preloaded MEMORY.md index
3. **Notebook context** — recent files, current field/section
4. **Capability block** — lists all connectors, agents, tools
5. **Thread context** — timestamp, tool profile, field scope

**Tool routing**: `decide_turn_shape(tool)` determines whether a tool call runs inline (synchronous) or gets dispatched as a task (long-running). The `dispatch_task` meta-tool is synthetic — its enum of task types is generated from the agent registry.

**Resolution post-back**: When a task completes, the orchestrator finds its origin thread (via `thread_tasks` join table) and appends a `task-resolved` message with widget data.

### Thread and chat system

**Threads** (`forge/thread_store.py`) persist conversations with variant-typed messages:
- `text` — plain assistant/user messages
- `widget` — rendered tool results
- `task-dispatched` — task creation notification
- `task-resolved` — task completion with result widget
- `memory-saved` — memory write notification

**Chat flow** (`forge/api/chat.py`):
1. POST `/api/chat` with `{ content, thread_id }`
2. Build system prompt via orchestrator
3. Stream through Anthropic SDK
4. On tool calls: execute inline or dispatch task
5. Stream tokens back to client via SSE
6. Persist turn to thread

### Notebook module

`forge/notebook/` — reads and writes the Obsidian vault.

**NotebookReader** (sync, uses ripgrep for search):
- `read(path)`, `list_dir(path)`, `exists(path)`, `search(query, prefix)`, `recent(section, limit)`, `resolve_wikilink(name)`
- Path validation rejects absolute paths and escapes

**NotebookWriter** (atomic writes via tempfile + os.replace):
- `ALLOWED_WRITE_PREFIXES = ("Wiki/", "Fields/", "Log/", "People/", "Projects/")`
- `write(path, content)`, `append(path, content)`
- Rejects paths outside the allowlist

### Memory module

`forge/memory/` — markdown files with YAML frontmatter, similar to Claude Code's memory format.

Each memory has a type (`user`, `feedback`, `project`, `reference`), a name, description, and body. `MEMORY.md` is an auto-generated index included in every system prompt.

### Claude Code runner

`forge/claude.py` spawns `claude --print --dangerously-skip-permissions` as a subprocess. Used by Code, Plan, Research, and Studio agents to run Claude Code in target directories (repos, vault, worktrees).

### Database

Async SQLite via aiosqlite. Schema created on startup with idempotent `ALTER TABLE` for evolution.

**Tables:** tasks, task_logs, threads, thread_messages, thread_tasks, schedules, todos, speedtest_results, chat_messages (legacy).

### Observability

Prometheus metrics at `/metrics`. Counters and histograms for:
- Task pipeline (total, duration, stage duration, queue depth, active count)
- Coordinator (tick count, tick duration)
- Chat (turns by shape, tool calls by connector, turn duration)
- Connectors (health gauge)
- Memory (reads, writes by type)
- Linear (poll results, tasks ingested)

Metrics are pre-registered on startup to avoid empty panels in Grafana.

---

## Frontend

SvelteKit 2 + Svelte 5 + Tailwind CSS 4 + TypeScript. Static adapter (pre-rendered, served by FastAPI).

### Routes

| Route | Purpose |
|-------|---------|
| `/today` | Daily dashboard: greeting, composer, yesterday summary, today shape |
| `/threads` | Thread list; `/threads/[id]` for conversation view |
| `/tasks` | Task list with status/type filters; `/tasks/[id]` for detail |
| `/library` | Vault browser, wiki viewer, field explorer, agent/connector views |
| `/settings` | App configuration |

### Key patterns

- **API client** (`ui/src/lib/api/`) — typed fetch wrapper, streaming via `AsyncGenerator`
- **State** — Svelte 5 runes (`$state`, `$derived`, `$effect`); stores for pinned items, sync, palette
- **Components** — `bits-ui` headless primitives, `phosphor-svelte` icons, `cva` for variants, `tailwind-merge` + `clsx` for class merging
- **Widgets** — `ui/src/lib/widgets/kernel/widget-host.svelte` dynamically renders task result widgets (weather, workouts, code-diff, etc.)
- **Storybook** — component development with mock data
- **E2E** — Playwright tests that fall back to mocks when the API is unreachable

### Data flow

```
User types in ThreadComposer
  → POST /api/chat (streaming)
  → Orchestrator assembles prompt + tools
  → Claude responds (tokens streamed to UI)
  → Tool call detected?
      ├─ Synchronous: execute inline, continue turn
      └─ Task dispatch: create Task, link to thread, nudge coordinator
          → Coordinator runs agent pipeline
          → post_resolution() appends task-resolved message to thread
          → UI polls/refreshes, renders widget
```

---

## Infrastructure

### NixOS deployment

Single NixOS host. `nix/services/ardent-forge.nix` defines the systemd service:

- **ExecStartPre**: `uv sync --frozen`, build UI if stale
- **ExecStart**: `op run --env-file forge.env -- uv run forge`
- **Secrets**: 1Password CLI injects env vars (Anthropic key, GitHub PAT, Linear key, Tavily key, Strava creds)
- **Hardening**: NoNewPrivileges, ProtectSystem=strict, ProtectHome=read-only, ReadWritePaths limited to `/data/ardent-forge`

**Other services**: Prometheus + Grafana (monitoring), notebook-sync (vault git backup), Caddy (reverse proxy + TLS), Ollama (optional local LLM).

---

## Security audit

Findings from a code review, ordered by severity.

### Critical

**Command injection in `forge/git.py`** — All git/gh operations use `asyncio.create_subprocess_shell()` with f-string interpolation. Parameters like `source`, `branch_name`, `title`, and `body` are not escaped (only `"` is escaped for commit messages). An attacker-controlled value in any of these fields could inject arbitrary shell commands.

- Lines 19, 28, 34, 37, 55, 66, 78, 81
- Fix: Replace `create_subprocess_shell()` with `create_subprocess_exec()` and pass arguments as a list, or use `shlex.quote()` for all interpolated values.

### High

**XSS via `{@html}` in `ui/src/lib/components/markdown.svelte`** — Markdown is rendered with `{@html marked.parse(...)}` without sanitization. The `convertWikilinks()` function also injects raw HTML from user-controlled notebook content. A wikilink like `[[test|<img onerror=alert(1)>]]` would execute as HTML since the display text is not escaped.

- Lines 13-17, 24
- Fix: Add DOMPurify or equivalent before `{@html}`. Escape the `label` variable in `convertWikilinks()`.

**No authentication** — All API endpoints are unauthenticated. Anyone with network access can read/write threads, tasks, memory, notebook content, and trigger LLM calls. Currently mitigated by network isolation (Tailscale/Caddy), but defense-in-depth is missing.

**Unvalidated column names in `forge/api/todos.py`** — The PATCH endpoint builds `SET {column} = ?` clauses from request keys without validating column names. While Pydantic's `TodoPatch` model constrains the field names (only `title`, `status`, `category`, `context`, `due_iso` survive `model_dump`), this is an implicit guarantee that breaks if someone adds a field without thinking about it.

- Line 97
- Fix: Add an explicit allowlist: `ALLOWED = {"title", "status", "category", "context", "due_iso"}`.

### Medium

**Path traversal in `forge/memory/__init__.py`** — The `_entry_path()` check (`self._root.resolve() not in path.parents`) is correct for most cases but doesn't cover the edge case where `path` resolves to exactly `self._root` itself. Also vulnerable to TOCTOU via symlinks.

- Lines 176-183
- Fix: Use `path.is_relative_to(self._root.resolve())` (Python 3.9+).

**Race conditions in coordinator** — No transaction handling around task state transitions. Two concurrent processes (e.g., coordinator tick + webhook) could process the same task simultaneously. The task refetch at line 171 doesn't null-check.

**No input length limits** — Task title/description, search queries, and cron expressions have no length validation. Could cause storage bloat or CPU exhaustion (regex via ripgrep).

### Low

- Metrics endpoint exposed without auth (information disclosure)
- No rate limiting on any endpoints
- Error messages in `git.py` may leak credentials embedded in repo URLs
- No CSRF protection (mitigated by same-origin if UI and API share host)
