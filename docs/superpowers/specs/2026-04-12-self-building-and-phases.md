# Ardent Forge — Self-Building Bootstrap and Phase Roadmap

**Date:** 2026-04-12
**Status:** Design

## Context

Plans 1–5 are complete: the Forge core, code handler, Linear integration, Web UI, and NixOS deployment all exist. Ardent Forge today can poll Linear for `devagent`-labeled issues, execute them against its own repo via the code handler, and ship PRs.

The next step is to stop hand-writing Linear tickets. This spec defines the **self-building bootstrap loop** — how Ardent Forge turns a spec into executing Linear tickets on its own — and catalogues the **phases** that follow, organized as three parallel tracks of work.

The framing shift from the earlier design: Ardent Forge is a **personal agentic OS**, not only a dev platform. Software development is one surface (the first, most complete one); a read/agent layer over the Notebook vault, a tool-using chat, and daily-rhythm agents are peers. Once the bootstrap loop exists, every subsequent surface is built by AF planning its own tickets.

## Phase 0 — The Self-Building Bootstrap Loop

### Goal

AF can take a spec in its own repo and turn it into executing Linear tickets, end-to-end, with one human review gate on the plan.

### Loop

```
1. Thomas writes docs/superpowers/specs/YYYY-MM-DD-foo.md
   frontmatter: status: draft
2. When ready, flips to status: ready-to-plan, commits, pushes
3. Coordinator spec-watcher polls AF repo main each tick
   Finds ready-to-plan specs with no existing plan → enqueues task(handler=plan)
4. plan handler:
     - clones ardent-forge into a worktree
     - reads the spec
     - calls Claude Opus to produce a plan markdown file in the existing
       docs/superpowers/plans/ format (numbered steps, acceptance criteria,
       test expectations)
     - writes plan file, bumps spec frontmatter to status: planned
     - opens PR "plan: <spec-title>"
     - task transitions to AWAITING_REVIEW
5. Thomas reviews the plan PR, comments inline, merges (or closes)
6. Coordinator plan-merge-watcher detects merged plan PRs with no
   corresponding Linear Project → enqueues task(handler=tickets)
7. tickets handler:
     - reads the merged plan markdown
     - creates a Linear Project under the AF team
     - creates one Linear Issue per numbered step
     - labels each "devagent", sets priority from step order,
       copies acceptance criteria to issue description,
       links back to plan file path
     - bumps spec frontmatter to status: executing, commits directly to main
8. Existing Linear poller picks up devagent issues
   → code handler executes each → PRs as today
9. On the last issue closing, spec frontmatter transitions to status: done
   (status sync from Linear completion)
```

### Spec Frontmatter State Machine

```
draft → ready-to-plan → planned → executing → done
```

- `draft` — ignored by the watcher. User is still writing.
- `ready-to-plan` — user-declared readiness. Watcher will pick this up.
- `planned` — plan PR exists (open or merged). Set by `plan` handler.
- `executing` — Linear tickets created. Set by `tickets` handler.
- `done` — all tickets closed. Set by status-sync.

The spec file is both the input to planning and the durable progress record.

### New Components

- **`plan` handler** (`forge/handlers/plan.py`) — Python. Clones repo, reads spec, calls Claude Opus with a decomposition prompt, writes plan markdown, bumps spec frontmatter, opens PR.
- **`tickets` handler** (`forge/handlers/tickets.py`) — Python. Parses plan markdown, calls Linear GraphQL, creates Project + Issues, bumps frontmatter. No LLM — pure mechanical translation.
- **Spec watcher** (coordinator tick addition) — scans `docs/superpowers/specs/*.md` on AF main for `status: ready-to-plan` without an existing plan file; enqueues `plan` tasks.
- **Plan-merge watcher** (coordinator tick addition) — scans AF main for merged plan files whose spec is `status: planned` and has no linked Linear Project; enqueues `tickets` tasks.

### Guardrails

The `plan` handler extends the self-modification allowlist with a narrow write scope:

- May write: `docs/superpowers/plans/*.md` (new files only), spec frontmatter edits to `docs/superpowers/specs/*.md`
- May not write: `nix/`, `forge/`, `tests/`, `ui/`, `scripts/`, or any file outside the allowlist above
- Enforced in the same module as the existing code-handler guardrails, as a handler-specific path allowlist

The `tickets` handler only writes the spec frontmatter bump and calls Linear — it does not touch any other files and is guarded accordingly.

### Model Choice

- **`plan`**: Claude Opus. Decomposition quality matters and runs at most once per spec.
- **`tickets`**: no LLM. Markdown parsing + Linear API calls.

### Fit With Existing Architecture

The coordinator, state machine, task store, handler registry, audit timeline, retry logic, and self-mod guardrails already exist and already support arbitrary handler types. `plan` and `tickets` are new registrations in that registry; they reuse the entire runtime. The Dashboard, Task Detail audit, and Linear status sync work unchanged.

## Phase Catalogue — Tracks After Bootstrap

Once Phase 0 lands, every subsequent phase is a spec Thomas writes and AF plans/executes. Phases are grouped as three tracks rather than one sequence, because they advance mostly independently.

### Track A — Code Reach

Extend the code handler beyond AF's own repo to the rest of Thomas's development work.

- **A1 — Multi-repo support.** `code` handler accepts a `repo` field on the task. Clones any named repo. Verification auto-detects per-repo (`./taskw`, `cargo`, `npm`, `uv` — existing auto-detect logic). Linear label `devagent:<repo-name>` routes to the right repo.
- **A2 — Cross-repo planning.** Plan handler learns to target repos other than AF when the spec declares `repo:` in frontmatter.
- **A3 — Non-AF review gates.** PRs on work repos may need per-repo verification config (existing CI, different reviewers).

### Track B — Knowledge Surface

Make the Notebook a first-class surface in AF. Obsidian remains the editor of record; AF is a view and agent layer.

- **B1 — Read-only Notebook view.** AF mounts `~/Notebook`. Renders Fields, Log, Projects, Wiki, People, Collections per the Notebook artboards. Today's Log on Dashboard. Full-text search. No editing from AF.
- **B2 — Quick capture.** The "What's on your mind?" box appends to today's Log (or to `Fields/Fleeting Thoughts/`, configurable). Plain markdown append. Obsidian Git commits normally.
- **B3 — Notebook agents.** A `notebook` handler: summarize a field, link related notes, draft a wiki article from a log entry, propose People touch-base reminders from Log mentions.

### Track C — Personal OS

The chat-with-tools and daily-rhythm surfaces from the artboards.

- **C1 — Chat tools baseline.** `@task @repo @file` mentions, `/tools` slash commands, thread persistence. Current chat streams text; this adds the tool-calling layer.
- **C2 — Structured renderers.** Typed blocks the chat can emit: weather, schedule, purchases, Linear state, task diff. Small composable components.
- **C3 — Scheduled agents.** The Agents page. Morning briefing (weather + today's Log + active tasks + calendar), evening shutdown (rollover prep), weekly review (field activity digest). Cron plus smart context.
- **C4 — Domain ingests.** Health (RENPHO CSV, workout logs), Finances (Monarch or CSV). Each a handler type that writes back into the corresponding Notebook field.
- **C5 — People CRM.** Agent watches Log for mentions, surfaces touch-base reminders, birthday prep, and draws on `/Fields/Gift Giving/` for gift ideas.

### Dependencies

- **A1 first** after Phase 0 — small spec, validates the planner decomposes real work correctly, unlocks Galley and dotfiles immediately.
- **B1 before most of B and C** — agents need to read the vault.
- **C1 before C2/C3** — chat tools are the substrate for renderers and scheduled agents.
- **C4/C5 last in Track C** — they assume B1 + C1 + C3.

### Suggested Order

1. Phase 0 — Bootstrap
2. A1 — multi-repo code
3. B1 — Notebook read-only view
4. C1 — Chat tools baseline
5. B2 + B3 + C2 + C3 in parallel, AF-planned, driven by attention

From Phase 0 onward, Thomas is the planner for what AF builds next — this roadmap is a default ordering, not a fixed schedule.

## Success Criteria

Phase 0 is complete when:

- A new spec with `status: ready-to-plan` on main produces a plan PR without human intervention.
- Merging that plan PR produces a Linear Project with one issue per step, each routed to the `code` handler.
- The spec frontmatter accurately reflects state through the full lifecycle.
- Guardrails prevent `plan` from writing outside the plan file and spec frontmatter, verified by tests.
- The full loop has been exercised end-to-end by using Phase 0 to generate the plan for A1 (multi-repo code).

The last bullet is the real test: Phase 0 proves itself by planning Phase A1.

## Out of Scope

- Notebook-native specs (planning non-code life work from `~/Notebook/Projects/`). May revisit later as a separate surface; for now, the bootstrap loop is repo-native only.
- Automatic replanning when tickets fail. Failed tickets route back to human review via the existing `code` handler error path. A future `replan` handler could be added if patterns emerge.
- Non-AF repo specs in Phase 0. Track A1 is where multi-repo planning enters.
