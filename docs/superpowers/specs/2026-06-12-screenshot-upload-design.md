---
name: screenshot-upload
description: Upload screenshots from a local browser to the NixOS box via a drag-and-drop modal that's always accessible from the sidebar. Timestamped files saved to ~/tmp/uploads/, cleaned up after 7 days, latest exposed via MCP tool.
type: design
---

# Screenshot Upload

## Why

Claude Code runs over SSH, so the usual "paste a screenshot" workflow doesn't work. This feature bridges that gap: drag a screenshot onto the Forge UI (accessible via Tailscale from any local device), and it lands on the box where Claude Code can read it.

## Backend

### Upload directory

Default: `Path.home() / "tmp" / "uploads"`. Configurable via `FORGE_UPLOAD_DIR` env var. Created on startup if it doesn't exist.

### `forge/api/uploads.py`

New `APIRouter(prefix="/api/uploads")` registered in `main.py`.

**`POST /api/uploads`**
- Accepts `multipart/form-data` with a single `file` field.
- Saves to the upload dir with a timestamped filename: `{stem}-{ISO8601}.{ext}` (e.g. `screenshot-2026-06-12T14-32-05.png`). Original extension preserved; stem defaults to `screenshot` if the upload has no meaningful name.
- Returns `{ "path": "/home/thomaseckert/tmp/uploads/screenshot-2026-06-12T14-32-05.png", "filename": "screenshot-2026-06-12T14-32-05.png" }`.

**`GET /api/uploads/latest`**
- Returns the most recently modified file in the upload dir: `{ "path": "...", "filename": "..." }`.
- Returns `404` if the directory is empty.

### Cleanup background task

An `asyncio` background task started in `main.py`'s lifespan. Runs immediately on startup, then every 24 hours. Deletes any file in the upload dir with `mtime < now - 7 days`. Logs deletions at `DEBUG` level. Does not recurse into subdirectories.

### MCP tool

`get_latest_upload` added to `forge/mcp/`. Calls the `UploadService` (or directly scans the upload dir) and returns the path to the most recent file. Allows any Claude Code session connected via MCP to retrieve the path without the user needing to paste it.

## Frontend

### `ui/src/lib/uploads/`

New feature folder following the existing lib structure.

**`upload-modal.svelte`**

A modal using the same custom scrim + card pattern as the command palette (fixed scrim, click-outside to close, card with `border border-[var(--color-stone)] rounded-[10px]`). Three states:

- `idle` — drag zone with "Drop image here" prompt and a "Browse" fallback button.
- `uploading` — spinner, filename shown.
- `done` — full file path displayed in a monospace block with a one-click copy-to-clipboard button. A "Upload another" link resets to `idle`.

Accepts an optional `file` prop (a `File` object). When provided, skips `idle` and begins upload immediately — used when the global drag handler pre-loads a file.

**`upload-trigger.svelte`**

Small icon button using `Image` from phosphor-svelte. Clicking opens the modal. Styled to match the existing sidebar footer link row (same `text-[12px] text-[var(--color-slate)] hover:bg-[var(--color-paper)]/60 rounded` pattern).

**`index.ts`**

Exports `UploadModal` and `UploadTrigger`.

### `app-shell.svelte` — global drag handler

Listens for `dragenter` and `dragleave` on `document` (added/removed in `onMount`/`onDestroy`). Tracks a depth counter: increment on `dragenter`, decrement on `dragleave`. When depth transitions 0→1, opens the modal (via a shared `uploadModalOpen` store). On `drop` at the document level (not consumed by the modal's drop zone), resets depth and closes.

This counter pattern prevents flicker from the pointer moving between child elements during a drag.

The modal's own drop zone calls `event.stopPropagation()` on `drop` so the document handler doesn't also fire.

### `sidebar.svelte`

Adds `<UploadTrigger>` in the footer section, above the Settings link.

### `api/client.ts`

Adds:

```ts
uploadFile(file: File): Promise<{ path: string; filename: string }>
```

Uses `FormData`; does not set `Content-Type` (browser sets it with the multipart boundary). Reuses the existing `API_BASE` constant.

## Claude Code integration

- `get_latest_upload` MCP tool lets Claude Code sessions call `mcp__forge__get_latest_upload` to retrieve the path of the most recent upload without the user needing to paste it.
- A note added to CLAUDE.md documents the `~/tmp/uploads/` convention: when the user mentions a screenshot, check there for the most recent file.

## Error handling

- Upload fails (non-OK response): modal shows an error message and returns to `idle` so the user can retry.
- Upload dir missing: backend creates it on startup; not a runtime concern.
- No uploads yet: `GET /api/uploads/latest` returns 404; MCP tool returns a descriptive message rather than an error.

## Out of scope

- Serving uploads back via HTTP (Claude Code reads files directly by path).
- Multi-file upload.
- Image preview in the modal.
- Upload history list in the UI.
