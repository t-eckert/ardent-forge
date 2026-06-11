---
name: forge-mcp-server
description: Expose Forge's functionality to Claude Code sessions running on the box via an MCP server. A FastMCP (official mcp Python SDK) streamable-HTTP app is mounted into the existing FastAPI app at /mcp, in-process, so tools call Forge's already-assembled services directly (TaskStore, MemoryStore, RepoRegistry, coordinator, connectors). Tools cover task dispatch + observation, memory read/write, repos & schedules, and (conditionally) notebook read + web search.
type: design
---

# Forge MCP Server

## Why

The box increasingly hosts long-running Claude Code sessions doing real development work — sessions started by hand, not just the agentic ones Forge dispatches. Those sessions have no way to reach Forge's state: the task pipeline, the shared memory store, the repo registry, cron schedules, the notebook. They duplicate context that Forge already holds.

An MCP server closes that gap. A Claude Code session on the box gets a `forge` MCP that lets it hand off long-running work to Forge's agents, share memory with chat/Linear-driven sessions, inspect the workspace, and read the notebook — all against the one live Forge process, with no second source of truth.

## Architecture

A new module `forge/mcp/` builds a **FastMCP** server using the official `mcp` Python SDK and exposes its **streamable-HTTP** app. That app is mounted into the existing FastAPI application at `/mcp`, in the same process. MCP tools therefore call Forge's already-assembled services directly — no second DB connection, no REST round-trip, no duplicated coordinator.

```
Claude Code session (on box)
        │  http://localhost:7030/mcp  (streamable HTTP)
        ▼
FastAPI app (forge.main) ── mount("/mcp") ──▶ FastMCP streamable-HTTP app
        │                                              │
        │  shared process / shared service instances   │
        ▼                                              ▼
TaskStore · MemoryStore · RepoRegistry · Coordinator · ConnectorRegistry
```

### Service injection

The MCP module follows the same configuration pattern as `forge/api/chat.py` (`chat.configure(...)`): a module-level `configure(...)` injects the assembled services after they exist in `main.py`'s lifespan. Tool functions read those module-level references. This keeps `forge/mcp/` import-light and avoids an import cycle with the coordinator.

The injected services:
- `store: TaskStore` — task CRUD + schedule CRUD
- `memory: MemoryStore` — markdown memory store
- `repo_registry: RepoRegistry` — workspace repo scan
- `coordinator` — for `nudge()` after dispatch (typed structurally as "has `.nudge()`", as chat does)
- `connectors: ConnectorRegistry` — for the optional web-search tool
- `notebook_reader: NotebookReader | None` — for the optional notebook tools

### Lifespan composition

FastMCP's streamable-HTTP transport requires its own session-manager lifespan (it runs a background task group for session management). Forge already defines a custom `lifespan` in `main.py`. The MCP session manager's lifespan must be composed into Forge's existing one so both start and stop cleanly — i.e. Forge's lifespan enters the MCP session manager's context (`async with session_manager.run():` or the SDK's documented equivalent) around its existing `yield`.

The mount and the `configure(...)` call happen inside the lifespan, after the services are assembled (after the orchestrator/coordinator block), so the injected references are live before the first request.

### Dependency

Add the official MCP SDK to `pyproject.toml` dependencies: `mcp>=1.2` (the package providing `mcp.server.fastmcp.FastMCP` and streamable-HTTP support). Pin to whatever current version exposes `streamable_http_app()` / the session-manager API used here; verify the exact symbol names against the installed version during implementation.

### Client setup

**On the box** (localhost):

```bash
claude mcp add --transport http forge http://localhost:7030/mcp
```

**From another tailnet device (e.g. the user's Mac).** Two paths, both already working given the current infra:

- **Through Caddy over HTTPS (recommended).** `nix/services/caddy.nix` reverse-proxies the catch-all `handle { }` block to `127.0.0.1:7030`, so `/mcp` is served under the existing Forge UI host with TLS via tailscaled certs:
  ```bash
  claude mcp add --transport http forge https://ardent-forge.feist-gondola.ts.net/mcp
  ```
- **Direct to port 7030.** `networking.firewall.trustedInterfaces = [ "tailscale0" ]` opens all ports over the Tailscale interface, so `http://ardent-forge:7030/mcp` (or the tailnet IP) works as plain HTTP.

**Caddy streaming check (implementation task).** Streamable-HTTP MCP uses long-lived SSE-style responses. Verify Caddy's `reverse_proxy` streams them through without buffering (it flushes by default, so this is expected to work — confirm with a real MCP client round-trip through the Caddy host, not just localhost).

## Tool surface

Each tool is a thin async wrapper over an existing service. Tool bodies are plain async functions (callable directly in tests without the transport). All tools return JSON-serializable dicts/lists.

### Tasks — dispatch + observe

- **`dispatch_task(type: str, title: str, description: str, repo: str | None = None)`**
  Builds a `Task` via `Task.new(...)` with `source=TaskSource.CHAT`, saves it through `store.save(task)`, then calls `coordinator.nudge()` so the coordinator starts processing within seconds instead of waiting a full poll tick. Mirrors the chat `dispatch_task` path in `forge/api/chat.py`, minus thread-linking (MCP sessions have no Forge thread). Returns the task id and status.
  Validation matches the REST layer: `title` ≤ 500 chars, `description` ≤ 50,000 chars, `type` ≤ 64 chars. A `type` that matches a `TaskType` member is coerced to the enum; otherwise the raw string is passed through (same as `CreateTaskRequest`).

- **`get_task(task_id: str)`**
  Returns the full task (`task.model_dump(mode="json")`), including `status`, `result`, and — for Code-agent tasks — `zellij_session` and `attach_cmd` so the caller can attach to a live session. Returns `{"error": "Task not found"}` if absent.

- **`list_tasks(status: str | None = None, type: str | None = None)`**
  Recent tasks for polling progress. Filters by status/type the same way the REST `list_tasks` does.

### Memory — shared with chat/Linear sessions

Over `MemoryStore`. Writes regenerate `MEMORY.md` automatically (existing store behavior).

- **`list_memory()`** → list of memory entries (filename, slug, name, description, type, updated_at).
- **`read_memory(filename: str)`** → full entry incl. body; `{"error": ...}` if not found.
- **`write_memory(name: str, description: str, type: str, body: str, filename: str | None = None)`** → writes/updates an entry. `type` must be one of `MemoryStore`'s `VALID_TYPES`.
- **`delete_memory(filename: str)`** → deletes; `{"error": ...}` if not found.

### Repos & schedules

- **`list_repos()`** → repos from `RepoRegistry.list()` (name, dev_port, env, label, etc.).
- **`get_repo(name: str)`** → single repo or `{"error": ...}`.
- **`list_schedules()`** → cron schedules via `store.list_schedules()`.
- **`create_schedule(name, cron_expr, task_type, repo=None, prompt_template=None, label=None)`** → builds the stored template the same way `forge/api/schedules.py::_build_template` does, then `store.save_schedule(...)`. Returns the created schedule.
- **`delete_schedule(schedule_id: str)`** → deletes; `{"error": ...}` if not found.

### Notebook & search — conditional

These tools are **registered only if the backing service is configured**, mirroring how connectors register in `main.py`. If unconfigured, the tool simply does not appear in `tools/list` rather than erroring at call time.

- **`search_notebook(query: str)`** / **`read_note(path: str)`** — read-only Obsidian access via `NotebookReader`. Registered only when `notebook_reader is not None`.
- **`web_search(query: str)`** — via `WebSearchConnector`. Registered only when the Tavily-backed connector is present in the registry.

## Behavior & intent

- **Polling, not push.** MCP cannot reliably push to a Claude Code session, so task completion is observed via `get_task` / `list_tasks`. The intended flow: dispatch → keep working → poll. Tool descriptions state this so the calling model uses them correctly.
- **Conditional registration** keeps the surface honest: a tool that can't work in the current deployment isn't advertised.

## Error handling

- Tools return structured error dicts (`{"error": "..."}`), never raise raw exceptions into the transport.
- Not-found cases (task, repo, memory, schedule) → `{"error": "<thing> not found"}`.
- Unconfigured services → tool not registered at all (handled at registration time, not call time).
- Input validation reuses the same Pydantic constraints as the REST layer (length caps, valid `task_type`, valid memory `type`). Invalid input → `{"error": "..."}` describing the violation.
- No new secret resolution happens through MCP; `op://` references stay inside the agent pipeline.

## Safety / exposure

The `/mcp` endpoint inherits Forge's existing security posture: bound to the host, reachable only over localhost / Tailscale, no separate authentication (same as every other Forge route today).

Stated plainly: this grants any local Claude Code session full read/write access to tasks, memory, and schedules. That matches the use case — the user runs these sessions themselves on the box — but it is the security boundary. If Forge's port is ever exposed more broadly, the MCP surface is exposed with it. No additional auth layer is in scope for this design.

## Testing

`tests/test_mcp.py`:

- **Per-tool unit tests** — call each tool's async function directly against in-memory `store` / `MemoryStore` fixtures (from `tests/conftest.py`). Cover: `dispatch_task` saves a task and nudges the coordinator (assert nudge called via a stub); `get_task` round-trips a saved task; not-found paths return `{"error": ...}`; memory write/read/delete; schedule create/delete; repo list/get.
- **Conditional registration** — assert notebook/web-search tools are present when their service is configured and absent when it is not.
- **Integration test** — mount the app, open an MCP client session against `/mcp`, assert `tools/list` returns the expected set, and run a `dispatch_task` → `get_task` round-trip through the transport.

Tests follow the existing suite conventions: pytest + pytest-asyncio (`asyncio_mode = "auto"`), in-memory SQLite, `respx` for any external HTTP.

## Out of scope

- Pushing task-completion notifications to MCP clients (polling only).
- Authentication / per-client authorization on `/mcp`.
- Triggering the synchronous chat orchestrator from MCP (only pipeline task dispatch).
- Exposing `op://` secret resolution as an MCP tool.
- UI changes.
