---
name: Architecture Restructuring - Ardent Forge, nb, and Homelab
description: Split Ardent Forge into two independent applications (Ardent Forge for agentic coding, nb for knowledge management) deployed on shared Homelab infrastructure
type: design
status: superseded
superseded_by: 2026-05-19-dev-toolbox-pivot.md
---

# Architecture Restructuring: Ardent Forge, nb, and Homelab

## Executive Summary

Restructure the current monolithic Ardent Forge into three independent systems:

1. **Homelab** — Shared NixOS infrastructure (Quadlet, nftables, monitoring, secrets)
2. **Ardent Forge** — Agentic coding and task execution control plane
3. **nb** — Personal knowledge management system (Zettelkasten-aware agents, Obsidian vault integration)

Both applications will use the same modular architecture pattern (agents, connectors, tools, coordinator). Both run as separate containers on Homelab. No cross-system APIs or shared state.

---

## System Scope and Boundaries

### Homelab (Shared Infrastructure)

**Location:** `~/Repos/github.com/t-eckert/homelab` (extracted from current Ardent Forge)

**Responsibilities:**
- NixOS flake with Quadlet configuration for rootless Podman
- Network security: nftables egress rules per container
- Secrets management: agenix for credential injection
- Observability stack: Grafana, Prometheus, Loki, Tempo
- Tailscale access layer
- Shared service containers: Ollama (embeddings)

**What it doesn't own:**
- Application logic
- Application-specific databases
- Application-specific connectors or tools

### Ardent Forge (Agentic Coding and Task Execution)

**Location:** New repo (or fresh branch in current repo as fresh start)

**Tech Stack:**
- **Backend:** Rust + Axum (async web framework)
- **Frontend:** Svelte 5 + SvelteKit (built to static dist within same repo)
- **Binary:** Single compiled binary that serves frontend + API
- **Database:** SQLite (WAL mode)

**Responsibilities:**
- **Task orchestration:** Linear as primary task source (poller)
- **Chat/threads interface:** Development interface for task creation and refinement
- **Session management:** Claude Code invocations in sandboxed containers
- **Workspace management:** Project containers, git worktrees, sandbox lifecycle
- **Agent framework:** Modular agents (Code, Plan, extensible) with connectors and tools
- **Streaming:** SSE for agent session events
- **Cost tracking:** Token usage and API cost attribution per session

**Data owned:**
- Session state (running, completed, failed, etc.)
- Task queue and history
- Thread messages (chat history)
- Cost metrics
- Linear integration state (last polled commit, etc.)

**Agents (starting set):**
- **Code** — Executes tasks via Claude Code in containerized environments
- **Plan** — Builds implementation plans for complex tasks
- (Additional agents TBD during implementation planning)

### nb (Personal Knowledge Management)

**Location:** Separate new repo

**Tech Stack:**
- **Backend:** Python + FastAPI
- **Database:** SQLite (FTS5 for search, vectors for embeddings, sidecar tables for typed data)
- **Messaging:** Telegram Bot API (long-polling, no public endpoint)
- **Vault:** Obsidian vault as filesystem + Git (no Local REST API at runtime)
- **Embeddings:** Ollama (shared container on Homelab) running nomic-embed-text-v2-moe

**Responsibilities:**
- **Vault integration:** Read/write to Obsidian vault via Git
- **Indexing:** Incremental FTS5 + vector index keyed on git diffs
- **Retrieval:** Hybrid BM25 + semantic with graph-aware expansion
- **Research ingestion:** PDF/URL/highlight → literature note + concept proposals
- **Agent framework:** Three logical agents (Librarian, Researcher, Companion) within single service
- **Chat interface:** Telegram Bot API for conversational access
- **Dashboards:** Domain-specific views (Strava activities, reading list, link queue, todos)
- **Proposals:** Agent-generated suggestions for backlinks, orphan resolution, note enrichment

**Data owned:**
- Vault index (FTS5, vectors, link graph)
- Chat turn history (Telegram)
- Proposal inbox (accepted/rejected history)
- Typed dashboards (Strava activities, books, links, todos)

**Agents (from research + your Notebook repo):**
- **Librarian** — Nightly: orphan detection, stale-note surfacing, tag normalization, health-check linting
- **Researcher** — Event-driven: ingest URLs/PDFs/highlights → literature + concept notes
- **Companion** — Long-poll chat: conversational access to vault with search/read/proposal tools
- (Additional agents reviewed from existing Notebook repo)

---

## Shared Architectural Pattern

Both Ardent Forge and nb follow the same internal structure:

```
Application Service
  ├─ Agents
  │  └─ Declare which pipeline stages they implement
  │     (triage, execute, verify, deliver)
  │
  ├─ Connectors
  │  └─ Register tools available to agents
  │     (e.g., vault filesystem, Linear API, Anthropic API)
  │
  ├─ Coordinator
  │  └─ Gate-sequencing (stage machine)
  │     Resolves agent context (which agents, which tools)
  │
  └─ Persistence
     └─ SQLite for structured state
```

**Ardent Forge pipeline:**
```
queued → triaging → executing → verifying → delivering → completed
                                                           ↑
failed ────────────────────── requeue ──────────────────┘
```

**nb agents** run independently (Librarian = cron, Researcher = queue, Companion = long-poll), not as a formal pipeline.

---

## Deployment Topology

```
NixOS Homelab (Bee Link)
│
├─ Tailscale (access)
├─ nftables (egress rules)
├─ Secrets (agenix)
│
└─ Quadlet Units (systemd-managed rootless Podman)
   │
   ├─ ardent-forge.container
   │  ├─ Rust binary (Axum + Svelte frontend)
   │  ├─ SQLite state DB
   │  ├─ REST API + SSE
   │  └─ Spawns project containers as siblings
   │
   ├─ nb.container
   │  ├─ Python FastAPI service
   │  ├─ SQLite index + dashboard DB
   │  ├─ Vault bind-mount (git-tracked)
   │  └─ REST API (internal agents)
   │
   ├─ ollama.container (shared)
   │  └─ nomic-embed-text-v2-moe
   │
   ├─ Monitoring
   │  └─ Grafana, Prometheus, Loki, Tempo
   │
   └─ Project containers (spawned by Ardent Forge)
      ├─ per-project dev environment
      ├─ git worktrees
      └─ Claude Code invocation
```

**Key decisions:**
- **Separate containers** for Ardent Forge and nb (independent lifecycles)
- **Shared Ollama** for embeddings (nb uses it; Ardent Forge doesn't need it yet)
- **Shared vault** bind-mount (read-write for nb; potentially read-only reference for Ardent Forge)
- **No cross-app APIs** — completely independent systems
- **Independent SQLite databases** — no shared persistence

---

## Data Flow

### Linear → Ardent Forge → Execution

```
Linear Issue
    ↓
[Linear Poller in Ardent Forge]
    ↓
Task: queued
    ↓
Coordinator (Code agent triage)
    ↓
Coordinator (Code agent execute) → spawn Claude Code session in project container
    ↓
SSE stream to UI + SQLite
    ↓
Coordinator (Plan agent verify)
    ↓
Task: completed (or failed → requeue)
    ↓
Result comment posted back to Linear
```

### Chat/Threads → Task Development → Execution

```
User message in chat UI
    ↓
[dispatch_task meta-tool or manual task creation]
    ↓
Task: queued + linked to thread
    ↓
Coordinator executes
    ↓
Result widget posted to thread
    ↓
User can refine, re-run, etc.
```

### nb Independent Loops

```
Librarian (cron, nightly):
  read vault → search index → detect orphans/stale notes → emit proposals

Researcher (event-driven):
  URL/PDF/highlight ingestion → Docling/readability → literature note + concepts

Companion (long-poll):
  Telegram message → search vault → format response → reply
```

---

## Build Sequencing (Rough Phasing)

**Phase 1 (Weeks 1-2): Foundation**
- Extract Homelab infrastructure (NixOS flake, Quadlet config, nftables)
- Verify rootless Podman, Ollama container, monitoring stack
- Establish shared patterns (secrets injection, container networking)

**Phase 2 (Weeks 2-3): Ardent Forge from scratch**
- Rust + Axum scaffold
- Svelte 5 frontend (built to dist within repo)
- Modular agent/connector framework
- Linear poller
- Code agent scaffold
- Chat/threads wired to task dispatch
- Project container spawning

**Phase 3 (Weeks 3-4): nb scaffold**
- Python + FastAPI scaffold
- Vault filesystem + Git integration
- SQLite schema (FTS5, vectors, link graph)
- Hybrid retrieval (BM25 + semantic + graph-walk)
- Librarian agent (nightly orphan detection)
- Telegram adapter (long-polling)
- OTel instrumentation

**Phase 4+: Agent refinement**
- Researcher agent (ingest pipeline with Docling)
- Companion agent (conversational chat)
- Additional agents from existing Notebook repo
- Dashboard views (Strava, books, links, todos)

---

## Technology Decisions

### Ardent Forge: Rust + Axum

**Why:**
- Single binary (frontend + backend in one)
- Async subprocess handling (core workload for streaming Claude Code output)
- Type safety
- User's existing Go/Rust experience transfers well
- Axum is battle-tested and performant

**Trade-off:**
- Frontend iteration slightly slower than Python/Node (no hot reload at development)
- Mitigation: Svelte's own dev server runs separately; build as part of CI

### nb: Python + FastAPI

**Why:**
- Faster iteration on agents and connectors
- Proven pattern from current Ardent Forge
- Excellent library ecosystem for NLP/indexing (transformers, sentence-transformers, LanceDB, etc.)
- Agent complexity will be higher; Python is the right tool for rapid prototyping

**Trade-off:**
- Separate runtime from Ardent Forge
- Mitigation: Homelab is single-machine; both run on the same box

### Both: SQLite (not Postgres)

**Why:**
- Single-user, single-machine scale
- WAL mode handles concurrent readers + one writer
- No operational overhead
- Native FTS5 for full-text search
- sqlite-vec or LanceDB for vectors in same transaction

**Constraints:**
- If either system ever needs write concurrency across machines, revisit
- For current single-homelab use case, it's the right call

---

## Key Constraints and Assumptions

1. **Linear is critical for Ardent Forge** — primary task source and execution context
2. **Chat/threads stays in Ardent Forge** — for task development and refinement
3. **nb is independent** — never calls Ardent Forge, never shared state
4. **Vault is owned by nb** — Ardent Forge may read it (future), but doesn't manage it
5. **All notebook agents move to nb** — from current Ardent Forge plus agents from Notebook repo
6. **Separate git repos** — Ardent Forge in one, nb in another, Homelab in its own
7. **Start from scratch** — no incremental migration; fresh implementations
8. **Deploy on same homelab** — both apps run on the Bee Link via Quadlet

---

## Open Questions for Implementation Planning

1. **Ardent Forge agents beyond Code/Plan:** What other agents should exist? (Scheduler, Reviewer, etc.)
2. **nb agents from Notebook repo:** Which existing agents transfer? Which are new?
3. **API boundaries:** Does nb expose any REST API for external clients, or is it internal-only?
4. **Monitoring:** What metrics matter most for each system? (session duration, cost, proposal acceptance rate, etc.)
5. **Telegrap long-polling vs webhooks:** For nb, is long-polling sufficient, or should we eventually add webhook support for lower latency?

---

## References

- ARDENT_FORGE.md — Detailed research on sandboxed agent control planes
- NOTEBOOK.md — Research on Zettelkasten-aware knowledge systems
- Current Ardent Forge codebase — Agent/connector/coordinator patterns to reuse
