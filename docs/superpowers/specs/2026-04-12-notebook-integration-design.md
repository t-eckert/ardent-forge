# Notebook Integration Design

**Date:** 2026-04-12
**Status:** Draft

## Summary

Give Ardent Forge read and write access to the user's Obsidian Notebook
(`github.com/t-eckert/Notebook`), so task handlers can draw context from
existing notes and deliver output (e.g. research results) into the vault.
Integration is filesystem-based: the Notebook is cloned onto the Bee
Link, kept in sync with the user's laptop via `syncshot`, and exposed to
forge as injectable `NotebookReader` / `NotebookWriter` services.

## Motivation

Two immediate use cases:
1. **Write target.** Research-type tasks produce markdown that belongs
   in `Wiki/` or `Fields/`. Without notebook integration those outputs
   have nowhere to land that's useful afterwards.
2. **Context source.** The Notebook encodes the user's people, projects,
   and prior learnings. Handlers working on tasks benefit from reading
   it before acting.

Two future use cases shape the design:
- Asking about the Notebook through chat ("what have I punted on
  recently?") — requires the reader to be usable outside task handlers.
- Browsing the Notebook inside the forge web UI — requires a stable,
  read-only API surface over the vault.

## Architecture

### On the box

- `/data/ardent-forge/notebook/` — clone of the Notebook repo, owned by
  the forge user.
- `ardent-forge-notebook-sync.service` — a new systemd service running
  `syncshot.py --period 30` against that directory. Authenticates with
  the existing `FORGE_GITHUB_TOKEN` from the 1Password service account.
  `ExecStartPre` clones the repo if the directory is empty.
- Forge reads and writes directly on the working tree. No worktrees, no
  feature branches: everything lands on `main` and syncshot commits it
  within the next tick.

Syncshot commits whatever is dirty each cycle, so concurrent handler
writes converge as long as they touch different files (they do — each
task owns its output path).

### In forge

A new `forge/notebook/` module:

- `NotebookReader` — read-only, first-class service (not handler-private).
  The chat endpoint and the future UI API both consume it.
- `NotebookWriter` — write access with an allowlist of top-level
  directories.
- Both are constructed once in `forge/app.py` and injected into the
  handler registry and any other consumer.

Configuration: `FORGE_NOTEBOOK_DIR` env var, default
`/data/ardent-forge/notebook`. If unset or missing on disk, the reader
and writer initialize as `None`, forge logs a warning, and any handler
that requires them triage-fails.

## Components

### `forge/notebook/reader.py`

```python
class NotebookReader:
    def __init__(self, root: Path): ...
    def read(self, path: str) -> str
    def list_dir(self, path: str) -> list[str]
    def search(self, query: str, path_prefix: str | None = None) -> list[SearchHit]
    def resolve_wikilink(self, name: str) -> Path | None
    def exists(self, path: str) -> bool
```

- All paths are relative to `root`. The reader rejects any path that
  resolves outside `root` (path-traversal guard).
- `search` shells out to `ripgrep`, returning file path + line number +
  matched line.
- `resolve_wikilink("OpenClaw")` searches for `OpenClaw.md` anywhere in
  the vault and returns its path, or `None` if it doesn't exist yet. If
  multiple files share the name, returns the shortest path (closest to
  root) — matches Obsidian's own resolution behavior.

### `forge/notebook/writer.py`

```python
ALLOWED_WRITE_PREFIXES = ("Wiki/", "Fields/", "Log/")

class NotebookWriter:
    def __init__(self, root: Path): ...
    def write(self, path: str, content: str) -> None
    def append(self, path: str, content: str) -> None
```

- `write` and `append` raise `NotebookWriteError` if `path` does not
  start with an allowed prefix, or resolves outside `root`.
- `+Templates/`, `+Assets/`, `+PDFs/`, `People/`, `Projects/`, and any
  `.base` file are off-limits.
- Writes are atomic: write to a temp file in the same directory, then
  `os.replace` into place. Prevents syncshot seeing a half-written file.

### Nix service: `nix/services/notebook-sync.nix`

- `systemd.services.ardent-forge-notebook-sync`
  - `Type = "simple"`, running `python3 syncshot.py --period 30`
  - `WorkingDirectory = /data/ardent-forge/notebook`
  - `EnvironmentFile` points at the existing `op`-rendered env file so
    `GITHUB_TOKEN` is available
  - `ExecStartPre` clones the repo if empty, configures
    `credential.helper` to use the token
  - `Restart = "on-failure"`, `RestartSec = 30`
- Syncshot source: vendored from `github.com/t-eckert/syncshot` (single
  file, stdlib-only — either copy `syncshot.py` into the repo or add it
  as a flake input).

## Data flow

Research-task example (the handler itself is out of scope for this
spec):

1. Task created with `type = "research"`, title "OpenClaw use cases".
2. `ResearchHandler.triage` — reads `Wiki/` and `Fields/` via
   `NotebookReader` to see what's already known.
3. `execute` — Claude runs web searches, drafts markdown, resolves
   wikilinks to existing entries where appropriate.
4. `verify` — markdown parses; wikilinked targets either exist or are
   deliberately new.
5. `deliver` — `writer.write("Wiki/OpenClaw.md", content)`.
6. Syncshot commits within 30s and pushes.
7. User's laptop syncshot pulls; file appears in Obsidian.

## Error handling

| Condition | Behavior |
|---|---|
| `read()` on missing path | raise `FileNotFoundError`; caller decides |
| `write()` path outside allowlist | raise `NotebookWriteError` with attempted path |
| Path traversal (`../`) in read or write | raise `NotebookWriteError` / `ValueError` |
| Syncshot auth/push failure | syncshot logs and keeps retrying; changes queue locally, no data loss |
| `FORGE_NOTEBOOK_DIR` unset or missing | reader/writer init as `None`; forge logs a warning; notebook-dependent handlers triage-fail |
| Ripgrep not installed | `search` raises at construction time (validated in `__init__`) |

NTFY alerting on repeated push failures is a future addition — v1 just
relies on syncshot's own logging, visible via `journalctl`.

## Testing

- Unit tests for `NotebookReader` and `NotebookWriter` use a temp-dir
  fake vault (`tmp_path`). Coverage:
  - Path traversal attempts on read and write
  - Allowlist enforcement on write (`Wiki/ok.md` accepted;
    `People/foo.md`, `+Templates/x.md`, `../etc/passwd` rejected)
  - Wikilink resolution: present, absent, ambiguous
  - Ripgrep-backed search returns expected hits; empty result when no
    match
- One integration test exercises the full syncshot loop against a local
  bare remote, verifying the systemd unit's auth configuration works.
- No mocking of the filesystem. Matches existing forge test style.

## Security

- Writes confined to an explicit allowlist of top-level directories.
- Path-resolution guard prevents writing outside the notebook root, even
  with crafted relative paths.
- Atomic writes prevent syncshot from committing partial files.
- Notebook clone lives under `/data/ardent-forge/notebook` with forge
  user ownership; no world-readable permissions.
- `FORGE_GITHUB_TOKEN` continues to be the sole secret; no new
  credentials introduced.

## Out of scope

Explicitly deferred to future specs:
- Semantic search / embedding index (the eventual "option C" upgrade to
  the reader).
- Chat endpoint consuming `NotebookReader` for natural-language queries
  over notebook content — supported by this design, but its own spec.
- UI file-browser and markdown rendering of the Notebook.
- The `research` task handler itself.
- NTFY alerting on notebook-sync failures.

## Open questions

None at spec time. Revisit if:
- Multiple concurrent writes to the same file become a real scenario
  (currently assumed not to happen).
- Syncshot's 30s period produces noticeable UX lag when the user is
  watching Obsidian.
