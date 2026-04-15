---
status: completed
title: Ardent Forge — the orchestrator
---

# Ardent Forge — Orchestrator Design Spec

**Date:** 2026-04-13
**Depends on:** `2026-04-12-connectors-and-flexible-agents.md` (Connectors + flexible agents refactor)

## Context

Ardent Forge's backend is reorganising around two primitives: **Connectors** (encapsulated external capabilities that provide tools) and **Agents** (specialist task processors with declared stages). That refactor describes *how work gets done*. This spec describes *who the user talks to* — the single conversational identity that orchestrates the system.

That identity is **Ardent Forge** itself. The user has one assistant. Agents never speak directly; Forge narrates on their behalf. Tools execute inline or via dispatched tasks, but there is only one voice in chat.

Forge's value is not that it knows more than a bare Claude — it's that it knows *you*: your projects, your training block, your repositories, your people, your preferences. It accumulates that knowledge across conversations via a layered memory system and gets more capable over time as connectors, agents, and memory all grow.

## Roles

Three roles, strictly separated:

| Role       | What it is                                                       | Has a voice? |
| ---------- | ---------------------------------------------------------------- | ------------ |
| Forge      | The conversational orchestrator. One Claude instance, one voice. | Yes — the only voice the user hears |
| Agent      | A specialist task processor (code-agent, research-agent, etc.)    | No — produces artifacts, not prose |
| Connector  | An encapsulated external capability (strava, github, weather)     | No — emits tool results, not prose |

Forge consumes both connectors' tools (directly in-turn) and agents' outputs (asynchronously via dispatched tasks). Agents and connectors are interchangeable to the user — they are implementation details of "how Forge got that answer."

## Turn Types

A single assistant turn is one of three shapes. Every turn is still a Claude `assistant` message; the discriminator is what the message *contains*:

### 1. Synchronous tool turn

Forge calls one or more connector tools inline and folds the result back into the same turn.

- **When**: the request is self-contained and fast — "what's the weather", "where can I get pizza", "what did I spend this week".
- **Shape**: prose + one or more `WidgetHost`-rendered tool payloads. Matches what we already have.
- **Latency budget**: tool results should return in seconds. If a tool call would take more than ~10s, Forge promotes the request to a task dispatch instead.

### 2. Task dispatch turn

Forge creates a `Task`, hands it to an agent, and returns a `task-dispatched` card. The conversation continues; execution is asynchronous.

- **When**: the work is heavy, long-running, requires multi-stage processing, or the user asked for a durable outcome (a PR, a notebook entry, a report).
- **Shape**: prose + a `task-dispatched` widget that shows the task id, the agent handling it, the declared stages, and a live-updating status.
- **UI contract**: the task card subscribes to task status updates. As the agent progresses through stages, the card updates inline. No new messages are posted during execution.

### 3. Task resolution turn

When a dispatched task completes (or fails), Forge posts a **resolution message** into the originating thread with the final artifact as a widget.

- **When**: an async task whose `origin_thread_id` points to a thread has reached a terminal state.
- **Shape**: prose narration ("`code-agent` finished — 4 files, +14/−14, tests green.") + artifact widget (e.g. `code.diff`).
- **Trigger**: posted by the coordinator, *authored by Forge*. Forge writes the narration; the coordinator inserts the message into the thread. From the user's perspective it's a seamless continuation of the same conversation.

Tasks created by *non-thread* origins (cron, watcher, webhook, direct API) do **not** post resolution messages. Their effect shows up in the relevant state surface — the Tasks list, the affected Field page, the Library log. Quiet by default.

## Memory

Forge has three layers of memory. They are distinct and serve different purposes.

### Layer 1 — Forge memory (curated)

Small markdown files Forge writes to record stable facts and preferences.

- **Storage**: on the box at `/data/ardent-forge/memory/`. Not checked into git (memory is personal, per-deployment, evolves continuously). Backed up alongside the task database via the existing `backup-agent` (B2 or equivalent), not synced through the notebook pipeline.
- **Format**: identical to the Claude Code memory format — frontmatter (`name`, `description`, `type`) + markdown body. Types: `user`, `feedback`, `project`, `reference`.
- **Index**: `MEMORY.md` at the root lists each file as a one-line pointer. Loaded into every conversation's system context.
- **Writes**: triggered by explicit user instruction ("remember that…"), by Forge's own judgment when it learns something durable, or when receiving correction. A memory-write surfaces in the thread as a small inline chip ("saved"), not a full widget.
- **Reads**: `MEMORY.md` preloaded; individual files fetched on demand when a relevant pointer matches the current query.
- **User control**: the entire store is user-visible and editable via `Library/Memory`. Every memory can be viewed, edited, or removed.

### Layer 2 — Notebook (read-only to Forge)

The user's own knowledge graph: daily logs, field pages, wiki articles, people, collections. Maintained by the user in Obsidian + synced into the notebook connector.

- **Access**: Forge has full read access via a `notebook` connector that exposes tools like `notebook.read_page`, `notebook.search`, `notebook.list_field`, `notebook.today_log`.
- **No writes**: Forge never edits notebook files as memory. If Forge wants to record something about the notebook, it writes a Forge memory with a pointer to the relevant page.
- **Distinction from memory**: the notebook is *what the user wrote*; memory is *what Forge learned about the user*.

### Layer 3 — Thread history (retrieval)

Every past thread is persistent and queryable.

- **Storage**: existing thread schema extended so threads, messages, and widget payloads are all addressable and searchable.
- **Access**: a `threads.search` tool or implicit retrieval Forge runs when the user refers to "last time" or "that PR we did." Narrower and more recent than memory — for episodic continuity rather than enduring preferences.
- **No preloading**: thread history is retrieved on demand; it doesn't inflate system context.

### Interaction between layers

```
  User asks: "how did we branch off main last time?"
   ├─ Forge preloaded system context has MEMORY.md (knows user prefers one-branch-per-feature)
   ├─ Forge retrieves from thread history → finds the rename/t-client thread
   ├─ Forge queries notebook → Redpanda field page lists current main commit
   └─ Forge responds with context-specific answer
```

## Voice & System Prompt

Forge has a consistent voice. It's the same voice as the italic subtitles on Today, the Playfair subheads in widgets, and the tone of narration around agent completions. Editorial, attentive, specific. Not chirpy; not corporate.

The system prompt assembly is layered:

```
[persona block]   — static, defines Forge's voice and principles
[memory block]    — MEMORY.md content (typically <200 lines)
[capability block] — registered connectors + agents + their tool schemas
[context block]   — thread metadata (toolProfile, field scope if any)
[history block]   — the thread's messages
```

The persona block names the three operating principles:

1. **One voice.** You narrate agent work; agents never speak directly. When an agent finishes, you report the outcome — you don't paste their output.
2. **Choose the right turn shape.** Synchronous tool call for quick facts. Task dispatch for durable, long-running, or multi-stage work. Don't make the user wait for something that belongs in a task.
3. **Learn durably, act lightly.** Write memory when you learn something stable. Don't flood memory with per-conversation trivia. Surface memory writes quietly.

## Task ↔ Thread Link

Tasks and threads relate many-to-many: a thread can dispatch many tasks over its lifetime, and while each task has a single *origin*, its outcome may be narrated into multiple threads (cross-referenced, shared, forked). Use a join table rather than a foreign-key column on `Task`.

```sql
CREATE TABLE thread_tasks (
  thread_id     TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
  task_id       TEXT NOT NULL REFERENCES tasks(id)   ON DELETE CASCADE,
  relation      TEXT NOT NULL CHECK (relation IN ('origin', 'referenced')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (thread_id, task_id, relation)
);
CREATE INDEX thread_tasks_task_id ON thread_tasks (task_id);
```

- `relation = 'origin'` — this thread created the task. At most one of these per task. Drives the resolution-message post-back on completion.
- `relation = 'referenced'` — this thread mentioned the task (e.g. a later thread links to an earlier task's PR). No post-back; just enables cross-thread navigation.

Queries both directions are cheap: `SELECT task_id FROM thread_tasks WHERE thread_id = ?` for a thread's tasks; index on `task_id` for the reverse.

The coordinator reads the origin relation to decide whether to post a resolution message:

```python
origin = store.get_origin_thread(task.id)  # None for cron/watcher/direct
if origin is not None:
    await store.post_resolution(thread_id=origin, task=task, narration=...)
```

**UI surfaces**:

- **In a thread**: dispatched tasks inline as live cards, resolved tasks as narration + artifact. The thread reads its `thread_tasks` rows to render the panel.
- **In Tasks surface**: a breadcrumb link back to the origin thread; a "referenced in" chip for threads that link to it.

## Capability Growth Loop

Forge becomes more capable through three channels, all accumulable:

| Channel    | What grows                                    | How                                                                    |
| ---------- | --------------------------------------------- | ---------------------------------------------------------------------- |
| Memory     | Forge's understanding of the user + projects  | Writes during conversation; edited by user in `Library/Memory`         |
| Connectors | External capabilities available as tools      | Registered at startup; user can add via guided connect flows in chat   |
| Agents     | Task types that can be dispatched             | Registered at startup; new task types enable new dispatch behaviors    |

A well-timed chat turn can trigger any of these. "I got a YNAB account" → Forge walks the user through OAuth → the `ynab` connector registers → its tools are live in the next turn → memory records the preference.

## UI Implications

This spec leaves the temporal spine intact (Today / Threads / Library / Tasks). Specific changes:

- **Assistant message variants**: `widget-turn`, `task-dispatch-turn`, `task-resolution-turn`, `memory-saved-chip`. All four render in the conversation under a single Forge avatar.
- **`Library/Memory`**: listing of all Forge memories grouped by type; each memory is viewable, editable, removable. A search bar and a "new memory" manual-entry path.
- **`Library/Agents`**: roster of registered agents (name, task_type, stages, connectors, recent runs) — doc-style. Not a spine item.
- **`Library/Connectors`**: integration status, OAuth health, setup / re-auth flows. Not a spine item.
- **Tasks surface** (replacing the Agents spine): live list of all tasks across all agents + manual + scheduled. Filter by status, agent, origin thread.
- **Task detail**: includes `origin_thread_id` breadcrumb back to the thread if present.

## What This Spec Does Not Define

- **Exact prompt wording for Forge's persona.** That's a tuning exercise; the spec says "there is a persona block" and its contents evolve.
- **Memory conflict resolution.** When Forge learns something that contradicts an existing memory, how does it decide to update? First pass: newest write wins, stamped with `updated` date; detect explicit user corrections as higher priority. Refinement lives in a later memory-management spec.
- **Tool budget per turn.** How many tool calls Forge is allowed to chain within one synchronous turn before escalating to a task. Needs empirical tuning.
- **Chat permissions model.** All connectors available to all threads. Per-thread connector scoping (e.g. "health+tools" thread only exposes health-related connectors) is a future enhancement.
- **Agent-to-agent orchestration.** An agent spawning sub-tasks. Out of scope here and in the connectors spec.

## Success Criteria

- A user sends a one-shot query ("what's the weather"). Forge answers in one synchronous turn with a `weather.forecast` widget. No task created.
- A user asks for heavy work ("rename tClient across the coordinator"). Forge creates a task, returns a `task-dispatched` card with live status, and — on completion — posts a resolution message with the `code.diff` artifact **in the same thread**.
- A cron-triggered `morning-briefing` task completes and updates state (Today's overnight panel refreshes, the notebook daily log gets appended) **without posting to any thread**.
- A user teaches Forge something about themselves ("I'm training for the Ottawa Race Weekend half"). Forge writes a memory; a subtle "saved" chip appears inline. Next conversation references this fact without being reminded.
- A user edits their memory in `Library/Memory`. The edit is reflected in Forge's next conversation.
- Adding a new connector requires no changes to Forge's code — its tools automatically become available to chat.
- Adding a new agent requires no changes to Forge's code — its task type becomes dispatchable automatically.
- The notebook is queryable by Forge but never written to by Forge. Memory writes go only to the memory store.

## Out of Scope

- **Multi-user support.** Forge is single-user. Memory, threads, and tasks are all scoped to one identity.
- **Offline mode.** Forge requires online connectors. A degraded-connectivity UX is a future topic.
- **Fine-tuning / custom models.** Forge runs on whatever Claude model the user configures. No custom training.
- **Proactive behavior without triggers.** Forge doesn't spontaneously message the user. All assistant turns are responses to user input or task completions tied to explicit threads.
