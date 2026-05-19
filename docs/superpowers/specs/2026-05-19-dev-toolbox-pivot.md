---
name: dev-toolbox-pivot
description: Reposition Ardent Forge from a notebook-centric agentic platform into a developer-toolbox control plane for a single NixOS box accessed over Tailscale. Drops containers, drops notebook-first framing, centers Zellij sessions and dispatched Claude tasks.
type: design
---

# Ardent Forge — Developer Toolbox Pivot

## Why

The earlier vision (see `2026-04-09-ardent-forge-design.md`, `2026-04-16-notebook-centric-vision.md`, `ARDENT_FORGE.md`) built around two ideas that no longer hold:

1. **Container-per-project isolation via rootless Podman + Quadlet.** Never built. The new model treats the whole NixOS box as nukable. Source of truth for code is GitHub. Source of truth for secrets is 1Password. There is no sandbox boundary worth maintaining; if the agent breaks something, we rebuild the box from Nix and re-pull from GitHub.
2. **Notebook as center of gravity.** The Obsidian notebook is a useful reference manual for project context, but it is not the platform's organizing principle. Daily-log writing, weekly reviews, people-tracking, life-coordination automation: out of scope. The notebook stays as a read surface that agents can consult.

The platform's actual job: be a control plane that makes a single NixOS dev box pleasant to use over SSH, lets dev servers reach me over Tailscale, and dispatches Claude Code tasks from chat, Linear, and cron.

## Use cases (locked)

1. **SSH + persistent Zellij sessions.** I `ssh box -t zellij attach <repo>` and pick up where I left off — both for manual editing and for watching an in-progress Claude task.
2. **Tailscale-exposed dev servers.** Each repo declares a dev port. Ardent Forge wires `tailscale serve` so `https://<repo>.<tailnet>.ts.net` reaches it. TLS via Tailscale.
3. **Notebook as reference manual.** Agents can read pages from the Obsidian vault as task context. No automated writes. No daily-log automation.
4. **Agentic Claude coding.** Three dispatch surfaces, one execution path:
   - Chat in the Ardent Forge UI → Code task → PR.
   - Linear issue gets a `claude` label or enters a configured status → Code task → PR + comment back on the issue.
   - Cron schedule fires → Code task with a saved prompt template against a saved repo.

## Decisions (locked)

| Question | Answer |
|---|---|
| Where does code live? | `~/Repos/<name>` (i.e. `/home/thomaseckert/Repos/<name>`). One git checkout per repo, shared between manual use and agent worktrees. |
| `workspace_dir` for Code agent? | `/home/thomaseckert/Repos`. Agent does `git worktree add ~/Repos/<name>/.worktrees/<task-id>` against the existing checkout. |
| How does Claude run? | Inside a Zellij pane, always. `zellij run --session <task-id> --layout agent.kdl -- claude --output-format stream-json …`. Stdout still tees to `sessions/<id>.jsonl` and broadcasts over SSE. |
| Sandboxing? | None. Box is nukable. Secrets injected as env vars per task; nothing persisted on disk. |
| Secrets source of truth? | 1Password. `op` CLI with a service-account token mounted from agenix at boot. Agents request secrets by `op://Vault/Item/field` reference; resolved to env vars at task start, not persisted. |
| Dev server exposure? | `tailscale serve` per repo with a MagicDNS hostname (`<repo>.<tailnet>.ts.net`). |
| Notebook scope? | Read-only API + agent tool. No writers. |
| Code source of truth? | GitHub (or other remote Git providers). Nothing important lives only on the box. |
| Auth on the UI? | None. Tailscale-bound only. |

## What changes

### Add

- **`forge/repos/`** — `RepoRegistry`: scan `~/Repos/*/.git` at startup, persist metadata in SQLite (`id`, `path`, `default_branch`, `dev_port`, `last_activity`), expose `/api/repos`. Optional per-repo `repo.yaml` in the repo root declaring `dev_port`, `claude_label`, `cron_tasks`, `allowed_op_paths`.
- **`forge/zellij/`** — wrapper over `zellij list-sessions` / `zellij attach` / `zellij run`. Layout templates:
  - `manual.kdl` — shell + editor pane, one long-lived session per repo, named `<repo>`.
  - `agent.kdl` — Claude pane + scratch pane, named per task `agent-<task-id>`.
- **`forge/connectors/onepassword.py`** — `OPConnector.resolve_refs(env) -> env`. Replaces `op://...` values via `op read`. Enforces per-repo `allowed_op_paths` allowlist from `repo.yaml`. Token loaded from agenix at process start.
- **`forge/tailscale/`** — declarative `tailscale serve` config generator. Watches the repo registry, regenerates serve config when `dev_port` changes. Surfaces port-conflict errors at config-time, not runtime.
- **Cron-driven schedules** — extend `forge/api/schedules.py`: schedule = `{ cron_expr, repo_id, prompt_template, label }`. Coordinator dispatches a Code task on each fire. UI at `/library/schedules`.
- **Linear-driven dispatch** — extend `forge/linear/poller.py`: on `claude` label or configured status transition, dispatch Code task with issue body + comments as prompt context. On task completion, post PR link + summary as Linear comment.

### Modify

- **`forge/agents/code.py`** — switch from raw subprocess to `zellij run --session agent-<task-id> --layout agent.kdl -- claude …`. Still streams stream-json from stdout. Result widget includes branch, PR link, attach command (`ssh box -t zellij attach agent-<task-id>`), and dev-server URL.
- **`forge/config.py:Settings.workspace_dir`** — default `/home/thomaseckert/Repos`.
- **`nix/services/ardent-forge.nix:FORGE_WORKSPACE_DIR`** — `/home/thomaseckert/Repos`.
- **`nix/home.nix:FORGE_WORKSPACE_DIR`** — `/home/thomaseckert/Repos`.
- **`nix/services/tailscale-portforward.nix`** — generate `tailscale serve` config from the repo registry instead of static port-forwarding.
- **`forge/api/notebook.py`** — read-only endpoints. Drop POST/PUT/DELETE.
- **`forge/notebook/`** — keep `reader.py`; archive `writer.py` (don't delete yet, in case targeted writes come back).
- **UI: `today/`** — repurpose as "Dashboard": active Zellij sessions, running tasks, dev-server status, recent commits across `~/Repos`.
- **UI: `/library/`** — keep `agents`, `connectors`, `memory`, `log`. Add `repos`, `schedules`. Remove the rest (see Cut).
- **`ARDENT_FORGE.md`** — rewrite to reflect this pivot. Keep §6 (prior-art survey) for reference; delete the container/quadlet/microVM/seccomp/SELinux chapters.
- **`CLAUDE.md`** — drop "centered around Obsidian notebook" framing; add Zellij / Tailscale-serve / 1Password / `~/Repos` sections.

### Cut

- `forge/agents/research.py`, `research_prompt.py` — notebook-flavored.
- `forge/agents/studio.py`, `studio_prompt.py` — notebook-flavored.
- `forge/connectors/weather.py`, `forge/api/weather.py`, `nix/services/the-weather.nix` — out of scope.
- `forge/api/fields.py`, `forge/api/todos.py` — notebook-flavored.
- UI routes: `library/wiki`, `library/people`, `library/fields` (and matching components).
- `nix/services/notebook-sync.nix` — drop the auto-sync; if I want the vault on the box, I'll `git pull` it manually or as a plain systemd timer.
- The "self-building" spec watcher flow in `forge/watchers/` — keep the spec watcher, drop the auto-plan/auto-implement chain. Plans get written; humans dispatch them.

### Leave alone

- FastAPI app structure, task pipeline, ThreadStore, chat dispatch wiring.
- SQLite + ULID + Pydantic v2 patterns.
- Tailscale, Caddy, monitoring, autodeploy, ollama, postgres nix services.
- The Linear poller and client (only the dispatch trigger changes).

## Phase plan

### Phase 1 — Foundation
- Add `forge/repos/` + `RepoRegistry`.
- Add `forge/zellij/` + layouts.
- Switch Code agent to run inside Zellij.
- Repoint `workspace_dir` to `~/Repos` in config, nix services, home.
- Update tests that pass fake `workspace_dir` (most already do — they use `tmp_path`).

### Phase 2 — Secrets + dev servers
- `forge/connectors/onepassword.py` + agenix secret for `OP_SERVICE_ACCOUNT_TOKEN`.
- Rewrite `nix/services/tailscale-portforward.nix` as a registry-driven `tailscale serve` generator.
- Add `repo.yaml` parsing and per-repo `allowed_op_paths` enforcement.

### Phase 3 — Dispatchers
- Cron-driven: extend `forge/api/schedules.py`; UI page.
- Linear-driven: extend `forge/linear/poller.py`; result-comment posting.
- Chat-driven: make Code agent the default chat dispatch target.

### Phase 4 — Slim down
- Remove cut agents, connectors, API routes, UI routes (see Cut).
- Repurpose `today/` route into Dashboard.

### Phase 5 — Docs
- Rewrite `ARDENT_FORGE.md`.
- Update `CLAUDE.md`.
- Mark `2026-04-16-notebook-centric-vision.md` and `2026-04-26-architecture-restructuring.md` as superseded by this spec.

## Risks

- **Zellij as a hard dependency for tasks.** The runner module must produce a clear error if `zellij` is missing and fall back to plain subprocess in tests/CI.
- **1Password service-account scope.** A leaky token reads every vault. Per-repo `allowed_op_paths` allowlist in `repo.yaml`, checked before resolution, contains the blast radius.
- **Tailscale serve port conflicts.** Two repos both declaring `:5173`. `repo.yaml` is the source of truth so we catch this at registry-load, not at dev-server-start.
- **Worktree dirty-state surprise.** If `~/Repos/<name>` has uncommitted changes and an agent task creates a worktree from `HEAD`, the agent doesn't see them. Standard git-worktree semantics; document but don't try to fix.
- **No sandbox = agent can rm -rf the box.** Accepted. Box is nukable, code is on GitHub, secrets are in 1Password. The blast radius is "rebuild from Nix, re-clone." This is the entire point.

## Out of scope (deliberate)

- Container-per-project, microVM isolation, seccomp, SELinux, capability dropping, nftables egress allowlists. The whole §2 + §3 of `ARDENT_FORGE.md` goes away.
- Daily logs, weekly reviews, book tracking, people CRM, life coordination automation. Notebook is read-only reference.
- Multi-user auth. Tailscale-only, solo operator.
- Postgres. SQLite WAL is fine.
- OTel/Tempo/Grafana stack beyond what already exists.
- Self-building / spec-watcher auto-implementation.

## Reference

- [netclode](https://stanislas.blog/2026/02/netclode-self-hosted-cloud-coding-agent/) — secret-proxy + Tailscale MagicDNS dev-server patterns.
- [Tony Dehnke iPhone + Zellij](https://tonydehnke.com/blog/claude-code-iphone-ssh-zellij/) — named persistent sessions + `rc`/`rj`/`rl` helpers.
- [Claude Code Scheduled Tasks](https://code.claude.com/docs/en/scheduled-tasks) — native routines; keeping our scheduler local for a single audit surface.
- [Managing NixOS over SSH with Claude Code](https://discourse.nixos.org/t/managing-multiple-nixos-machines-with-claude-code-via-ssh/74259) — adjacent pattern for the box managing itself.
