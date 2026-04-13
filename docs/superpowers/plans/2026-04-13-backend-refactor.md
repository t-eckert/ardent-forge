# Backend Refactor — Connectors · Agents · Orchestrator

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development`. Steps use `- [ ]` syntax.

**Executes against:**
- `docs/superpowers/specs/2026-04-12-connectors-and-flexible-agents.md`
- `docs/superpowers/specs/2026-04-13-forge-orchestrator.md`

**Goal.** Reshape the backend around three primitives (Connector, Agent, Forge-orchestrator) so the UI reframe (Tasks spine, memory, threads) has real endpoints behind it.

**Strategy.** Refactor in dependency order: connectors first (foundation), then agents (replaces handlers), then orchestrator (new surface), then persistence (threads, tasks-thread link, memory), then API endpoints. Each phase keeps the existing task pipeline working end-to-end.

---

## Phase A — Connectors

Foundation for every external capability. Weather migrates first as proof; future connectors slot in.

- [ ] Create `forge/connectors/__init__.py` with `Connector` Protocol, `Tool` dataclass, `ConnectorRegistry`.
- [ ] `Tool.to_anthropic_schema()` — emit Claude `tool_use` schema.
- [ ] `ConnectorRegistry.setup_all()` — call `setup()` on every registered connector during lifespan.
- [ ] `ConnectorRegistry.health_check()` — aggregate health; expose as `GET /api/connectors/health`.
- [ ] Migrate `forge/tools/weather.py` → `forge/connectors/weather.py` as `WeatherConnector`; preserve behaviour.
- [ ] Wire registry in `forge/main.py` lifespan; register WeatherConnector.
- [ ] Update `forge/api/chat.py` to pull tools from `connector_registry.all_tools()` — remove the per-tool `if block.name == "get_weather"` dispatch.
- [ ] Delete `forge/tools/` once callers migrate.
- [ ] Unit tests: registry register/get/all_tools/tools_for; weather connector setup + health + execute.

**Exit criteria:** `/api/chat` still answers weather queries identically; adding a connector requires one file + one registration.

---

## Phase B — Flexible agents

Replace the rigid four-stage `TaskHandler` with stage-declared `Agent`.

- [ ] Create `forge/agents/__init__.py` with `Agent` Protocol, `AgentContext` dataclass, `AgentRegistry`.
- [ ] `AgentContext` carries resolved tools (from `connector_registry.tools_for(agent.connectors)`), store, settings, and a reference to the orchestrator for memory lookups if needed.
- [ ] Update `forge/coordinator.py` for stage-aware processing:
  - Only call stages listed in `agent.stages`.
  - Skip state transitions for stages that don't run.
  - Allow `QUEUED → EXECUTING` when `triage` is absent.
- [ ] Migrate handlers to agents, one per commit:
  - [ ] `CodeAgent` — stages `[triage, execute, verify, deliver]`, connectors `[github]`.
  - [ ] `PlanAgent` — stages `[execute, verify, deliver]`, connectors `[github]`.
  - [ ] `ResearchAgent` — stages `[execute, verify]`, connectors `[websearch, notebook]`.
  - [ ] `TicketsAgent` — stages `[execute, deliver]`, connectors `[linear]`.
  - [ ] `EchoAgent` — stages `[execute]`, connectors `[]`.
- [ ] Wire `agent_registry` in `main.py`; register all agents.
- [ ] Update `state.py` transitions to allow skip-ahead when stages are absent.
- [ ] Delete `forge/handlers/`.
- [ ] Unit tests per agent; integration test: full task lifecycle for each.

**Exit criteria:** every existing task type produces byte-identical results to pre-refactor; coordinator metrics only record stages that actually ran.

---

## Phase C — Forge orchestrator

The conversational surface becomes its own module with defined turn shapes and memory access.

- [ ] Create `forge/orchestrator/__init__.py`:
  - `ForgeOrchestrator` class.
  - System prompt builder that assembles the 5 layered blocks (persona · memory · capability · context · history).
  - Turn-shape router: synchronous tool / task dispatch / task resolution.
- [ ] `forge/orchestrator/persona.py` — static persona block. Voice principles + "you narrate agents, agents never speak" rule.
- [ ] `forge/orchestrator/system_prompt.py` — `build_system_prompt(memory_index, connectors, agents, thread_meta)` returning the full prompt.
- [ ] `forge/orchestrator/dispatch.py` — heuristics + Claude decision for deciding synchronous-tool vs. task-dispatch. First version: simple rule (any tool whose `execute` is declared `long_running=True` → dispatch; otherwise synchronous). Refine later.
- [ ] `forge/orchestrator/narration.py` — agent-output → narration prose. Given a completed `Task` and its artifact, produce the prose line for the resolution message ("`code-agent` finished — 4 files, +14/−14, tests green.").
- [ ] Update `forge/api/chat.py` to route through `ForgeOrchestrator.handle_turn(thread_id, user_message)` instead of calling Claude directly.
- [ ] Unit tests: system prompt assembly; dispatch decision; narration output.

**Exit criteria:** a chat turn against weather returns a synchronous widget; a chat turn requesting code work creates a task and returns a dispatch card.

---

## Phase D — Threads, tasks ↔ threads, messages

Persist the conversational surface properly and join it to the task table.

- [ ] Schema: `threads` table (`id`, `title`, `kind`, `last_activity_at`, `unread`). Existing `chat_messages` becomes `thread_messages` with a `thread_id` FK.
- [ ] Schema: `thread_tasks` join table per the spec:
  ```
  (thread_id, task_id, relation) — relation ∈ {origin, referenced}
  ```
- [ ] `Task` gains no new columns; the relation lives entirely in `thread_tasks`.
- [ ] `ThreadStore`: `create`, `get`, `list`, `list_messages(thread_id)`, `append_message`, `link_task(thread_id, task_id, relation)`, `tasks_for_thread(thread_id)`, `origin_thread_for(task_id)`.
- [ ] Coordinator wiring: when a task completes, look up its origin thread; if present, call `ForgeOrchestrator.post_resolution(thread_id, task)` which writes a new `thread_messages` row with narration + artifact payload.
- [ ] Migration: existing `chat_messages` rows get attributed to a default thread id on upgrade.
- [ ] Unit tests: join table CRUD; resolution post-back.

**Exit criteria:** a chat turn that dispatches a task and waits → the resolution shows up in the same thread asynchronously.

---

## Phase E — Forge memory

Filesystem-backed curated memory store on the box.

- [ ] Storage path: `/data/ardent-forge/memory/`. Configurable via env for local dev.
- [ ] `MemoryStore` class:
  - `read_index() -> str` — read `MEMORY.md`.
  - `list() -> list[MemoryEntry]` — scan directory, parse frontmatter.
  - `get(filename) -> MemoryEntry`.
  - `write(entry: MemoryEntry) -> None` — writes file + appends to `MEMORY.md`.
  - `remove(filename) -> None`.
- [ ] `MemoryEntry` dataclass matches the Claude Code format: `name`, `description`, `type`, `body`.
- [ ] Tool: `forge.memory.write` — exposed as a pseudo-tool Forge can call in a turn to save a memory. Surfaces as a `memory-saved` chip in the UI.
- [ ] Orchestrator system-prompt builder preloads `MEMORY.md` and fetches individual entries on demand when their descriptions match the current query (simple keyword match v1).
- [ ] API endpoints for `Library/Memory` UI: `GET /api/memory`, `GET /api/memory/{name}`, `PUT /api/memory/{name}`, `DELETE /api/memory/{name}`, `POST /api/memory` (manual creation).
- [ ] `backup-agent` wiring: include `/data/ardent-forge/memory/` in the B2 backup target.
- [ ] NixOS config: ensure `/data/ardent-forge/memory/` exists with right ownership at provisioning time.
- [ ] Unit tests: CRUD; index regeneration after write.

**Exit criteria:** `curl /api/memory` returns the index; memory writes during a chat turn appear in the next conversation's context.

---

## Phase F — API surface for the UI reframe

New and reshaped endpoints the UI plan depends on.

- [ ] `GET /api/tasks` — list with filters (status, kind, agent, origin_thread_id). Paginated.
- [ ] `GET /api/tasks/{id}` — full detail incl. steps, metas, artifact payload.
- [ ] `POST /api/tasks` — manual task creation (used by Todos → Task promotion later).
- [ ] `GET /api/tasks/{id}/stream` — SSE status updates for the dispatch-card live update.
- [ ] `GET /api/threads` — list.
- [ ] `GET /api/threads/{id}` — metadata + messages.
- [ ] `POST /api/threads` — new thread.
- [ ] `POST /api/threads/{id}/messages` — user message. Streams Forge's response (synchronous tool or dispatch card).
- [ ] `GET /api/threads/{id}/tasks` — tasks joined to this thread.
- [ ] `GET /api/fields` — list of registered fields; `GET /api/fields/{slug}` — field metadata + query tools to fetch field content.
- [ ] `GET /api/connectors` + `GET /api/connectors/health` — roster + live health.
- [ ] `GET /api/agents` — roster (name, stages, connectors, recent runs).
- [ ] `GET /api/memory` — index + entries.
- [ ] Integration tests per endpoint.

**Exit criteria:** all UI-mocked data shapes have a real endpoint that returns the same schema-valid JSON.

---

## Phase G — Observability + backup wiring

- [ ] Prometheus metrics: per-agent stage durations; per-connector tool call count; memory read/write counts; task dispatch vs. synchronous turn ratio.
- [ ] Loki log labels: `agent_name`, `connector_name`, `turn_type`, `thread_id`.
- [ ] Grafana: new dashboard for orchestrator (turns/min, dispatch ratio, memory writes, resolution latency).
- [ ] `backup-agent` includes memory dir + task DB + threads DB in B2 target; verify restore path.

**Exit criteria:** dashboards populate; backup runs include all three stores; a test restore on a dev box produces a working Forge.

---

## Dependencies + ordering

```
A (connectors)
  └─ B (agents) — needs Connector protocol
       └─ C (orchestrator) — needs Agent + Connector
            ├─ D (threads + join) — needs orchestrator to post resolutions
            ├─ E (memory) — needs orchestrator to consume MEMORY.md
            └─ F (API) — needs D + E complete to expose real data
                 └─ G (observability + backup)
```

Phases A and B can be reviewed in isolation; nothing else ships until both land. C can start once B is green. D and E are independent of each other and can parallelise after C. F follows both. G closes the loop.

---

## Out of scope for this plan

- UI work — tracked separately in `2026-04-13-ui-reframe.md`.
- Strava / YNAB / GitHub-full / Linear connectors — each gets its own small plan; this refactor only migrates `weather` as proof of shape.
- Agent-to-agent orchestration.
- Memory conflict resolution beyond newest-wins + user corrections.
- Per-thread connector scoping.
