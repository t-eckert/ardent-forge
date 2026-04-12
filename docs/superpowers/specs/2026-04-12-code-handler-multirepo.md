---
status: ready-to-plan
title: Code handler multi-repo support (A1)
---

# Code handler multi-repo support (A1)

## Context

`CodeHandler` already accepts `task.repo`, clones any URL, and auto-detects per-repo verification commands (`./taskw`, `cargo`, `npm`, `uv`). The limitation is upstream: the Linear poller creates tasks with `repo=None`, so every Linear issue today either targets the AF self-repo implicitly or fails triage.

This spec extends the Linear poller to route issues to arbitrary repos via a label convention, and makes the AF self-repo the default when no routing label is present (backwards compatible).

This is the first phase Ardent Forge plans for itself — the self-referential validation of Phase 0.

## Goal

A Linear issue labeled `repo:owner/name` produces a task whose `code` handler clones `owner/name` and ships a PR there. Issues without a `repo:` label continue to target `t-eckert/ardent-forge`.

## Design

### Label convention

Issues opt into a target repo via a label named exactly `repo:<owner>/<name>` — for example `repo:t-eckert/galley` or `repo:t-eckert/dotfiles`. Only one `repo:` label is honored per issue; if multiple are present the poller picks the first and logs a warning.

The existing `devagent` label continues to gate which issues the poller picks up at all. `repo:` is a routing label, orthogonal to `devagent`.

### Poller changes

`forge/linear/poller.py` gains a helper `_extract_repo(issue) -> str | None` that scans `issue["labels"]["nodes"]` for names matching the prefix `repo:`. When found, returns the suffix (`owner/name`). When absent, returns `None`.

`LinearPoller.poll` passes the extracted value to `Task.new(repo=...)`. When `None`, `Task.new` is called with `repo=DEFAULT_REPO` where `DEFAULT_REPO = "t-eckert/ardent-forge"` is a module constant.

### Handler and GitOps behaviour

No changes to `CodeHandler`, `GitOps`, or verification. The existing code path already clones `https://github.com/{task.repo}.git`, creates a worktree, runs Claude, auto-detects verification, and opens a PR on `{task.repo}`.

### Config

`forge/config.py` gains a `default_code_repo: str = "t-eckert/ardent-forge"` setting so the default is overridable without a code change. The poller reads it from settings and uses it as the fallback.

### Auth

Non-AF repos need a GitHub token with PR write access. The existing `FORGE_GITHUB_TOKEN` (1Password) is already in the service environment. Assumed to be scoped broadly enough for any repo in `t-eckert/*` — if a specific repo rejects the push, the code handler's existing error path surfaces it as a failed task, no silent breakage.

## Out of Scope

- Cross-repo planning (A2) — specs targeting non-AF repos. This spec is only about Linear → code handler routing.
- Per-repo review config (A3).
- Validation that the `repo:owner/name` label points to a real, accessible repo. Trust-then-fail: a bad repo name surfaces as a clone failure, visible in the task audit timeline.
- Multiple repos per issue.
- Using `repo:` labels on the AF repo to route away from AF — if both `devagent` and `repo:foo/bar` are set on an issue created in the AF team, honor the `repo:` label.

## Tests

- `_extract_repo` returns `owner/name` when a single `repo:` label is present.
- `_extract_repo` returns `None` when no `repo:` label is present.
- `_extract_repo` with multiple `repo:` labels returns the first and logs a warning.
- `LinearPoller.poll` sets `task.repo = "t-eckert/galley"` when the issue has `repo:t-eckert/galley`.
- `LinearPoller.poll` sets `task.repo` to the configured default when no `repo:` label is present.
- Config default is `t-eckert/ardent-forge` and can be overridden via `FORGE_DEFAULT_CODE_REPO`.

## Acceptance

An issue in the Ardent Forge Linear team labeled `devagent` + `repo:t-eckert/galley` with a trivial task description (e.g., "update README") produces a PR on `t-eckert/galley`, not `t-eckert/ardent-forge`. An issue labeled only `devagent` continues to produce a PR on `t-eckert/ardent-forge`.
