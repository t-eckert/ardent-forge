# Research Handler Design

**Date:** 2026-04-12
**Status:** Draft

## Summary

Add a `research` task handler that delegates open-ended research to
Claude Code (web search + synthesis) and lands the output as a markdown
file in the user's Obsidian Notebook. Follows the existing 4-stage
handler shape (triage / execute / verify / deliver) and reuses the
`ClaudeRunner` subprocess wrapper already used by `CodeHandler`.

## Motivation

Research tasks exist in the task UI today but fail with "No handler
registered for type 'research'" because no handler is implemented. The
Notebook integration (shipped 2026-04-12) now gives us a write target
— this spec defines the handler that produces that content.

Example task: "OpenClaw Use Cases — collect blog posts, YouTube videos,
make a summary. Give me specific references so I can dig deeper on my
own."

## Architecture

### Execution model

The handler spawns the `claude` CLI as a subprocess inside the notebook
working tree (`/data/ardent-forge/notebook`). Claude reads the vault's
own `CLAUDE.md`, uses `WebSearch` and `WebFetch` tools to gather
information, and writes the output file directly on disk via its
`Write` tool. This matches the `CodeHandler` pattern exactly — the only
differences are the working directory, the prompt, and the
verification logic.

No git branching: research writes go directly to `main` of the Notebook
repo. Syncshot (running as its own systemd service) picks up the change
and pushes to GitHub within ~30 seconds.

### Dependencies

Constructor takes:
- `claude_runner: ClaudeRunner` — shared subprocess wrapper
- `notebook_root: Path` — the vault's filesystem root
- `claude_timeout: int = 600` — longer than CodeHandler's 300s; web
  research tends to take longer than local code work.

Both are constructed in `forge/main.py` and registered with the
`HandlerRegistry`. If the notebook is disabled (`FORGE_NOTEBOOK_DIR`
missing or unreadable), the handler is not registered at all — tasks
with `type=research` will fail with the existing "No handler registered"
message rather than a more specific "notebook disabled" path. Symmetric
with how `CodeHandler` requires a workspace.

## Components

### `triage(task)`

Returns `True` iff:
- `task.title` is non-empty.

Declines otherwise.

Notebook availability is a *registration-time* check (above), not a
triage-time check — the handler simply won't exist if the notebook
isn't configured.

### `execute(task)`

1. Snapshot the set of files under `Wiki/`, `Fields/`, `Log/` in the
   vault (recursive listing; a set of relative path strings).
2. Build the research prompt (see below).
3. Run `claude_runner.run(prompt, notebook_root)` with the handler's
   timeout.
4. On `TimeoutError` or `RuntimeError`, retry up to twice with
   `retry_context` appended to the prompt (mirrors `CodeHandler`).
5. Snapshot again, compute the set difference: files that exist after
   but did not exist before.
6. Return `{"claude_output": output[:2000], "new_files": sorted(list(new_files))}`.

### `verify(task)`

Passes iff:
- At least one entry in `handler_data["new_files"]` exists and starts
  with `Wiki/`, `Fields/`, or `Log/`.
- Each such file is at least 200 bytes on disk (stub guard, not a
  quality gate).

Otherwise fails.

### `deliver(task)`

For each file in `handler_data["new_files"]` under an allowed prefix:
- `path`
- `word_count` — whitespace-split count of the file contents
- `preview` — first ~500 characters of the file

Returns:
```
{
  "status": "delivered",
  "files": [{path, word_count, preview}, ...],
  "notebook_commit_pending": true
}
```

No git operations. Syncshot handles the commit + push asynchronously.

### Prompt

New helper `build_research_prompt(title, description, retry_context=None)`
in a new file `forge/handlers/research_prompt.py` (keeping it beside
the handler, paralleling how `build_prompt` lives in `forge/claude.py`
next to `ClaudeRunner`).

Template:

```
# Research Task: {title}

## Description
{description}

## Instructions
- You are working inside an Obsidian vault (the user's personal notebook).
- Read ./CLAUDE.md first for the vault's conventions on Wiki vs Fields vs Log.
- Use WebSearch and WebFetch to gather information from authoritative sources.
- Synthesize findings into a single markdown file.
- Decide the best path: Wiki/ for transferable knowledge, Fields/ for ongoing life areas.
  Never write to People/, Projects/, +Templates/, +Assets/, or any .base file.
- Use [[Wikilinks]] when referencing concepts or people that may already exist in the vault.
- Include specific references (URLs, titles, authors) so the user can dig deeper.
- Do not commit; just write the file.
```

If `retry_context` is set (a string describing the previous failure),
it's appended as a `## Previous Attempt` section.

## Data flow

1. Task created (via chat UI or Linear poll) with `type=research`.
2. Coordinator dequeues it, calls `ResearchHandler.triage()` → `True`.
3. Status transitions to `EXECUTING`. `execute()` runs Claude in the
   notebook dir, captures new files.
4. Status transitions to `VERIFYING`. `verify()` checks the new files.
5. Status transitions to `DELIVERING`. `deliver()` builds summaries.
6. Coordinator calls `mark_completed` with `final_result` = `execute`
   result merged with `deliver` result.
7. Syncshot commits and pushes within 30s. The file appears in the
   user's Obsidian vault after their local syncshot pulls.

## Error handling

| Condition | Behavior |
|---|---|
| Empty task title | `triage` declines; coordinator marks failed with "Handler declined during triage" |
| Notebook disabled at startup | Handler not registered; generic "no handler" failure |
| Claude subprocess timeout or crash | Retry up to 2 times with retry_context; then raise; coordinator marks failed |
| Claude writes zero new files | `verify` fails; task marked failed with "Verification failed" |
| Claude writes a file under `People/` or other forbidden dir | `verify` fails (no new files in *allowed* prefixes); the file is still on disk and syncshot will commit it; user cleans up manually via git. Not worth cleanup automation for v1. |
| Claude writes a stub file (< 200 bytes) | `verify` fails |

## Testing

- Unit tests in `tests/test_research_handler.py` using a `tmp_path`
  fake vault and a stubbed `ClaudeRunner`.
- **Triage:** declines on empty title; passes otherwise.
- **Execute:** stubbed runner writes `Wiki/Foo.md`; assert
  `new_files == ["Wiki/Foo.md"]` and `claude_output` is in the result.
- **Execute retry:** stubbed runner raises twice then succeeds; assert
  success after retry.
- **Verify:** passes when a new file exists under `Wiki/` with >200
  bytes; fails when no new files; fails when a new file is only 50
  bytes; fails when the only new file is under `People/`.
- **Deliver:** summaries include correct word count and preview; the
  preview is truncated at ~500 chars.
- No integration test spawning real `claude` CLI. Matches CodeHandler.

## Security

- No new secrets required. The `claude` CLI uses whatever auth is
  already configured on the box.
- The handler never executes arbitrary paths — verification reads
  files strictly under `notebook_root`.
- The notebook allowlist is enforced at the verify stage (not the
  write stage, because Claude writes directly). Forbidden-dir writes
  will land on disk but are detected and cause task failure. A future
  improvement could add a post-hoc cleanup step; out of scope here.

## Out of scope

- Cleanup of files written to forbidden directories (manual for v1).
- Rich markdown validation (structure, link resolution, formatting).
- Multi-file outputs with cross-links (handler expects one file per
  task).
- A separate concurrency policy for research tasks (shares the
  coordinator's `max_concurrent`).
- Chat-over-notebook ("what have I punted on recently?") — separate
  spec, mentioned in the notebook-integration spec's future notes.

## Open questions

None at spec time. Revisit if:
- 600s timeout proves insufficient for real research tasks.
- Claude frequently writes to the wrong top-level dir and users want
  automatic cleanup or retry-with-hint.
