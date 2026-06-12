# Screenshot Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a drag-to-open screenshot upload modal with a persistent sidebar trigger, timestamped file storage on the box, 7-day cleanup, and an MCP tool so Claude Code can retrieve the latest upload path.

**Architecture:** A new `UploadService` handles all file I/O; a thin FastAPI router wraps it for the browser; a background asyncio task runs daily cleanup. On the frontend, a module-level Svelte 5 `$state` store coordinates modal open/close across the sidebar trigger, the app shell drag handler, and the modal component itself.

**Tech Stack:** Python 3.13, FastAPI, aiosqlite (backend); SvelteKit 2 / Svelte 5, Tailwind CSS 4, phosphor-svelte (frontend); FastMCP (MCP tool).

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `forge/uploads.py` | `UploadService`: dir management, save, get-latest, cleanup |
| Create | `forge/api/uploads.py` | `POST /api/uploads`, `GET /api/uploads/latest` |
| Create | `tests/test_upload_service.py` | Unit tests for `UploadService` |
| Create | `tests/test_api_uploads.py` | HTTP tests for upload router |
| Modify | `forge/config.py` | Add `upload_dir` setting |
| Modify | `forge/main.py` | Register router, start cleanup task, wire MCP |
| Modify | `forge/mcp/server.py` | Add `get_latest_upload` tool |
| Modify | `CLAUDE.md` | Note about `~/tmp/uploads/` convention |
| Create | `ui/src/lib/uploads/state.svelte.ts` | Shared open/close state for modal |
| Create | `ui/src/lib/uploads/components/upload-modal.svelte` | Modal: drop zone, uploading, done states |
| Create | `ui/src/lib/uploads/components/upload-trigger.svelte` | Sidebar icon button |
| Create | `ui/src/lib/uploads/index.ts` | Barrel exports |
| Modify | `ui/src/lib/icons/index.ts` | Add `Image`, `Copy`, `Upload` icons |
| Modify | `ui/src/lib/api/client.ts` | Add `uploadFile()` |
| Modify | `ui/src/lib/chrome/components/sidebar.svelte` | Add trigger to footer |
| Modify | `ui/src/lib/chrome/views/app-shell.svelte` | Global drag handler + render modal |

---

## Task 1: UploadService

**Files:**
- Create: `forge/uploads.py`
- Create: `tests/test_upload_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_upload_service.py
import os
import time
from pathlib import Path

import pytest

from forge.uploads import UploadService


@pytest.fixture
def upload_dir(tmp_path):
    return tmp_path / "uploads"


@pytest.fixture
def service(upload_dir):
    return UploadService(upload_dir)


def test_ensure_dir_creates_directory(service, upload_dir):
    assert not upload_dir.exists()
    service.ensure_dir()
    assert upload_dir.is_dir()


def test_save_file_returns_path_with_timestamp(service):
    path = service.save_file(b"data", "screenshot.png")
    assert path.exists()
    assert path.suffix == ".png"
    assert "screenshot-" in path.name


def test_save_file_preserves_extension(service):
    path = service.save_file(b"data", "capture.jpg")
    assert path.suffix == ".jpg"


def test_save_file_uses_screenshot_stem_for_unnamed_file(service):
    path = service.save_file(b"data", "")
    assert path.stem.startswith("screenshot-")


def test_save_file_writes_content(service):
    content = b"\x89PNG content"
    path = service.save_file(content, "image.png")
    assert path.read_bytes() == content


def test_get_latest_returns_none_when_empty(service):
    service.ensure_dir()
    assert service.get_latest() is None


def test_get_latest_returns_most_recent(service):
    service.save_file(b"first", "a.png")
    time.sleep(0.05)
    p2 = service.save_file(b"second", "b.png")
    assert service.get_latest() == p2


def test_delete_old_files_removes_stale(service, upload_dir):
    service.ensure_dir()
    old_file = upload_dir / "old.png"
    old_file.write_bytes(b"old")
    old_time = time.time() - 8 * 86400  # 8 days ago
    os.utime(old_file, (old_time, old_time))

    deleted = service.delete_old_files(max_age_days=7)

    assert deleted == 1
    assert not old_file.exists()


def test_delete_old_files_keeps_recent(service, upload_dir):
    service.ensure_dir()
    new_file = upload_dir / "new.png"
    new_file.write_bytes(b"new")

    deleted = service.delete_old_files(max_age_days=7)

    assert deleted == 0
    assert new_file.exists()


def test_delete_old_files_returns_zero_when_empty(service):
    service.ensure_dir()
    assert service.delete_old_files() == 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_upload_service.py -v
```

Expected: `ModuleNotFoundError: No module named 'forge.uploads'`

- [ ] **Step 3: Implement UploadService**

```python
# forge/uploads.py
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)


class UploadService:
    def __init__(self, upload_dir: Path) -> None:
        self._dir = upload_dir

    def ensure_dir(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, content: bytes, original_name: str) -> Path:
        self.ensure_dir()
        suffix = Path(original_name).suffix if original_name else ""
        if not suffix:
            suffix = ".png"
        stem = Path(original_name).stem if original_name else ""
        if not stem:
            stem = "screenshot"
        ts = time.strftime("%Y-%m-%dT%H-%M-%S")
        dest = self._dir / f"{stem}-{ts}{suffix}"
        dest.write_bytes(content)
        return dest

    def get_latest(self) -> Path | None:
        self.ensure_dir()
        files = [f for f in self._dir.iterdir() if f.is_file()]
        if not files:
            return None
        return max(files, key=lambda f: f.stat().st_mtime)

    def delete_old_files(self, max_age_days: int = 7) -> int:
        self.ensure_dir()
        cutoff = time.time() - max_age_days * 86400
        deleted = 0
        for f in self._dir.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                log.debug("Deleted old upload: %s", f.name)
                deleted += 1
        return deleted
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_upload_service.py -v
```

Expected: all 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add forge/uploads.py tests/test_upload_service.py
git commit -m "feat: add UploadService for timestamped screenshot storage"
```

---

## Task 2: Upload API router

**Files:**
- Create: `forge/api/uploads.py`
- Create: `tests/test_api_uploads.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_api_uploads.py
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from forge.api import uploads as uploads_api
from forge.uploads import UploadService


@pytest.fixture
def upload_dir(tmp_path):
    return tmp_path / "uploads"


@pytest.fixture
def service(upload_dir):
    return UploadService(upload_dir)


@pytest.fixture
async def client(service):
    app = FastAPI()
    uploads_api.set_service(service)
    app.include_router(uploads_api.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_upload_returns_path_and_filename(client):
    resp = await client.post(
        "/api/uploads",
        files={"file": ("screenshot.png", b"\x89PNG", "image/png")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "path" in data
    assert "filename" in data
    assert data["filename"].endswith(".png")
    assert "screenshot-" in data["filename"]


async def test_upload_stores_file_content(client, upload_dir):
    content = b"\x89PNG\r\ntest content"
    await client.post(
        "/api/uploads",
        files={"file": ("image.png", content, "image/png")},
    )
    files = list(upload_dir.iterdir())
    assert len(files) == 1
    assert files[0].read_bytes() == content


async def test_get_latest_returns_404_when_no_uploads(client):
    resp = await client.get("/api/uploads/latest")
    assert resp.status_code == 404


async def test_get_latest_returns_most_recent(client):
    await client.post("/api/uploads", files={"file": ("a.png", b"first", "image/png")})
    import time; time.sleep(0.05)
    await client.post("/api/uploads", files={"file": ("b.png", b"second", "image/png")})

    resp = await client.get("/api/uploads/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert "path" in data
    assert "b-" in data["filename"]  # most recent file starts with "b"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_api_uploads.py -v
```

Expected: `ImportError` or `AttributeError` — router doesn't exist yet

- [ ] **Step 3: Implement the router**

```python
# forge/api/uploads.py
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from forge.uploads import UploadService

router = APIRouter(prefix="/api/uploads")

_service: UploadService | None = None


def set_service(service: UploadService) -> None:
    global _service
    _service = service


def _svc() -> UploadService:
    if _service is None:
        raise HTTPException(status_code=503, detail="Upload service not configured")
    return _service


@router.post("")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    path = _svc().save_file(content, file.filename or "")
    return {"path": str(path), "filename": path.name}


@router.get("/latest")
async def get_latest():
    path = _svc().get_latest()
    if path is None:
        raise HTTPException(status_code=404, detail="No uploads found")
    return {"path": str(path), "filename": path.name}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_api_uploads.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add forge/api/uploads.py tests/test_api_uploads.py
git commit -m "feat: add upload API router (POST /api/uploads, GET /api/uploads/latest)"
```

---

## Task 3: Config, main.py wiring, cleanup task

**Files:**
- Modify: `forge/config.py`
- Modify: `forge/main.py`

- [ ] **Step 1: Add `upload_dir` to config**

In `forge/config.py`, add this field after `memory_dir`:

```python
    # Screenshot uploads — timestamped files; cleaned up after 7 days
    upload_dir: str = "~/tmp/uploads"
```

- [ ] **Step 2: Verify config test passes**

```bash
uv run pytest tests/test_config.py -v
```

Expected: PASS (the new field has a default so no test changes needed)

- [ ] **Step 3: Wire uploads into main.py**

In `forge/main.py`, add the import at the top with the other api imports:

```python
from forge.api import (
    agents as agents_api,
    chat,
    connectors as connectors_api,
    health,
    memory as memory_api,
    notebook as notebook_api,
    repos as repos_api,
    schedules,
    tasks,
    threads as threads_api,
    uploads as uploads_api,   # add this line
    weather as weather_api,
)
```

Add `uploads` to the `include_router` block in `create_app()` (after `weather_api.router`):

```python
    app.include_router(uploads_api.router)
```

- [ ] **Step 4: Add cleanup helper and lifespan wiring**

In `forge/main.py`, add this helper function just before the `run()` function (at module level, after `create_app`):

```python
async def _upload_cleanup_loop(service) -> None:
    while True:
        n = service.delete_old_files(max_age_days=7)
        if n:
            logging.getLogger(__name__).info("Cleaned up %d old upload(s)", n)
        await asyncio.sleep(86400)
```

In the `lifespan` function, add the following block just after `await db.initialize()`:

```python
        from forge.uploads import UploadService
        upload_service = UploadService(Path(settings.upload_dir).expanduser())
        upload_service.ensure_dir()
        uploads_api.set_service(upload_service)
        upload_cleanup_task = asyncio.create_task(_upload_cleanup_loop(upload_service))
```

Then add cleanup before `await db.close()`:

```python
        upload_cleanup_task.cancel()
        try:
            await upload_cleanup_task
        except asyncio.CancelledError:
            pass
```

- [ ] **Step 5: Verify server starts without error**

```bash
uv run forge &
sleep 2
curl -s http://localhost:7030/api/uploads/latest | python3 -m json.tool
kill %1
```

Expected: `{"detail": "No uploads found"}` with status 404 (server runs, endpoint responds)

- [ ] **Step 6: Commit**

```bash
git add forge/config.py forge/main.py
git commit -m "feat: wire UploadService into Forge startup with daily cleanup task"
```

---

## Task 4: MCP tool

**Files:**
- Modify: `forge/mcp/server.py`

- [ ] **Step 1: Add `_upload_service` global and update `configure()`**

In `forge/mcp/server.py`, add `_upload_service = None` to the module-level globals block (after `_notebook_reader = None`):

```python
_upload_service = None
```

Update the `configure()` signature to accept `upload_service`:

```python
def configure(
    *,
    store=None,
    memory=None,
    repo_registry=None,
    coordinator=None,
    connectors=None,
    notebook_reader=None,
    upload_service=None,
) -> None:
    """Inject live services. Idempotent merge — only overwrites what's passed."""
    global _store, _memory, _repo_registry, _coordinator, _connectors, _notebook_reader, _upload_service
    if store is not None:
        _store = store
    if memory is not None:
        _memory = memory
    if repo_registry is not None:
        _repo_registry = repo_registry
    if coordinator is not None:
        _coordinator = coordinator
    if connectors is not None:
        _connectors = connectors
    if notebook_reader is not None:
        _notebook_reader = notebook_reader
    if upload_service is not None:
        _upload_service = upload_service
```

- [ ] **Step 2: Add the `get_latest_upload` tool function**

Add this function after `web_search` (before `build_mcp_server`):

```python
async def get_latest_upload() -> dict:
    """Return the path to the most recently uploaded screenshot.

    The user uploads screenshots via the Forge web UI. Call this whenever the
    user mentions a screenshot or asks you to look at an image — it returns
    the path of the most recent upload so you can read it with the Read tool."""
    if _upload_service is None:
        return {"error": "upload service not configured"}
    path = _upload_service.get_latest()
    if path is None:
        return {"error": "No uploads found — ask the user to upload a screenshot via the Forge UI"}
    return {"path": str(path), "filename": path.name}
```

- [ ] **Step 3: Register the tool in `build_mcp_server`**

In `build_mcp_server`, add after `server.add_tool(delete_schedule, name="delete_schedule")`:

```python
    server.add_tool(get_latest_upload, name="get_latest_upload")
```

- [ ] **Step 4: Pass `upload_service` to `mcp_configure` in `main.py`**

In `forge/main.py`, find the `mcp_configure(...)` call in the lifespan and add `upload_service=upload_service`:

```python
        mcp_configure(
            store=store,
            memory=memory_store,
            repo_registry=repo_registry,
            coordinator=coordinator,
            connectors=connectors,
            notebook_reader=notebook_reader,
            upload_service=upload_service,
        )
```

- [ ] **Step 5: Run MCP tests**

```bash
uv run pytest tests/test_mcp.py -v
```

Expected: all existing MCP tests PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add forge/mcp/server.py forge/main.py
git commit -m "feat: add get_latest_upload MCP tool"
```

---

## Task 5: CLAUDE.md note

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add upload convention note**

In `CLAUDE.md`, find the `## Key Patterns` section and add this bullet at the end of the list:

```markdown
- **Screenshot uploads**: when the user mentions a screenshot or image, call `mcp__forge__get_latest_upload` to get the path, then use `Read` to view it. Files land in `~/tmp/uploads/` with ISO-timestamped names; the MCP tool always returns the most recent one.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add screenshot upload convention to CLAUDE.md"
```

---

## Task 6: Frontend icons + API client

**Files:**
- Modify: `ui/src/lib/icons/index.ts`
- Modify: `ui/src/lib/api/client.ts`

- [ ] **Step 1: Add missing icons to the index**

In `ui/src/lib/icons/index.ts`, add `Image`, `Copy`, and `Upload` to the `export { ... } from 'phosphor-svelte'` block. Add them in the `// Misc semantic` group:

```typescript
	// Misc semantic
	Check,
	Circle,
	Copy,
	Dot,
	Image,
	Sparkle,
	Upload
```

- [ ] **Step 2: Add `uploadFile` to the API client**

In `ui/src/lib/api/client.ts`, add this method to the `api` object (after `toggleSchedule`):

```typescript
  // Uploads
  async uploadFile(file: File): Promise<{ path: string; filename: string }> {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/api/uploads`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "Unknown error");
      throw new ApiError(res.status, text);
    }
    return res.json();
  },
```

Note: no `Content-Type` header — the browser sets it automatically with the multipart boundary when using `FormData`.

- [ ] **Step 3: Typecheck**

```bash
cd ui && pnpm check
```

Expected: no type errors

- [ ] **Step 4: Commit**

```bash
git add ui/src/lib/icons/index.ts ui/src/lib/api/client.ts
git commit -m "feat: add upload icons and uploadFile API client method"
```

---

## Task 7: Upload state store

**Files:**
- Create: `ui/src/lib/uploads/state.svelte.ts`

- [ ] **Step 1: Create the state file**

```typescript
// ui/src/lib/uploads/state.svelte.ts

let open = $state(false);

export const uploadState = {
  get open() {
    return open;
  },
  show() {
    open = true;
  },
  hide() {
    open = false;
  },
};
```

- [ ] **Step 2: Typecheck**

```bash
cd ui && pnpm check
```

Expected: no errors

---

## Task 8: Upload modal component

**Files:**
- Create: `ui/src/lib/uploads/components/upload-modal.svelte`

- [ ] **Step 1: Create the modal**

```svelte
<!-- ui/src/lib/uploads/components/upload-modal.svelte -->
<script lang="ts">
	import { uploadState } from '../state.svelte';
	import { api } from '$lib/api';
	import { Image, X, Copy, Check } from '$lib/icons';
	import { Spinner } from '$lib/components';
	import { Heading, Body } from '$lib/typography';

	type UploadPhase = 'idle' | 'uploading' | 'done';

	let phase: UploadPhase = $state('idle');
	let uploadedPath = $state('');
	let uploadedFilename = $state('');
	let errorMsg = $state('');
	let copied = $state(false);
	let dragOver = $state(false);

	function reset() {
		phase = 'idle';
		uploadedPath = '';
		uploadedFilename = '';
		errorMsg = '';
		copied = false;
		dragOver = false;
	}

	function handleClose() {
		reset();
		uploadState.hide();
	}

	async function uploadFile(file: File) {
		phase = 'uploading';
		errorMsg = '';
		try {
			const result = await api.uploadFile(file);
			uploadedPath = result.path;
			uploadedFilename = result.filename;
			phase = 'done';
		} catch (e) {
			errorMsg = e instanceof Error ? e.message : 'Upload failed';
			phase = 'idle';
		}
	}

	function handleScrimDrop(e: DragEvent) {
		e.preventDefault();
		const file = e.dataTransfer?.files[0];
		if (file) uploadFile(file);
	}

	function handleZoneDrop(e: DragEvent) {
		e.preventDefault();
		e.stopPropagation();
		dragOver = false;
		const file = e.dataTransfer?.files[0];
		if (file) uploadFile(file);
	}

	function handleFileInput(e: Event) {
		const file = (e.target as HTMLInputElement).files?.[0];
		if (file) uploadFile(file);
	}

	async function copyPath() {
		await navigator.clipboard.writeText(uploadedPath);
		copied = true;
		setTimeout(() => (copied = false), 2000);
	}
</script>

{#if uploadState.open}
	<!-- Scrim — also catches drops outside the card -->
	<div
		class="fixed inset-0 z-50 bg-[rgba(26,23,20,0.38)] flex justify-center items-center px-4"
		onclick={handleClose}
		ondrop={handleScrimDrop}
		ondragover={(e) => e.preventDefault()}
		role="presentation"
	>
		<!-- Card -->
		<div
			class="w-full max-w-[480px] bg-[var(--color-paper)] border border-[var(--color-stone)] rounded-[10px] overflow-hidden shadow-[0_24px_80px_rgba(26,23,20,0.22)]"
			onclick={(e) => e.stopPropagation()}
			role="presentation"
		>
			<!-- Header -->
			<div
				class="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]"
			>
				<Heading size="sm">Upload Screenshot</Heading>
				<button
					onclick={handleClose}
					class="text-[var(--color-graphite)] hover:text-[var(--color-ink)] transition-colors"
					aria-label="Close"
				>
					<X size={16} />
				</button>
			</div>

			<!-- Body -->
			<div class="px-5 py-6">
				{#if phase === 'idle'}
					<div
						class="flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-lg py-10 px-6 transition-colors cursor-pointer
							{dragOver
							? 'border-[var(--color-ink)] bg-[var(--color-bench)]'
							: 'border-[var(--color-stone)] hover:border-[var(--color-slate)]'}"
						ondrop={handleZoneDrop}
						ondragover={(e) => { e.preventDefault(); e.stopPropagation(); dragOver = true; }}
						ondragleave={(e) => { e.stopPropagation(); dragOver = false; }}
						role="presentation"
					>
						<Image size={32} weight="light" class="text-[var(--color-graphite)]" />
						<Body size="sm" muted>Drop an image here</Body>
						<label class="cursor-pointer">
							<span class="text-xs text-[var(--color-ink)] underline underline-offset-2"
								>or browse</span
							>
							<input
								type="file"
								accept="image/*"
								class="sr-only"
								onchange={handleFileInput}
							/>
						</label>
					</div>
					{#if errorMsg}
						<p class="mt-3 text-xs text-red-500">{errorMsg}</p>
					{/if}
				{:else if phase === 'uploading'}
					<div class="flex flex-col items-center gap-3 py-8">
						<Spinner />
						<Body size="sm" muted>Uploading…</Body>
					</div>
				{:else}
					<div class="flex flex-col gap-4">
						<Body size="sm" muted>Saved to:</Body>
						<div
							class="flex items-center gap-2 bg-[var(--color-bench)] rounded px-3 py-2 font-mono text-[11px] text-[var(--color-ink)] break-all"
						>
							<span class="flex-1">{uploadedPath}</span>
							<button
								onclick={copyPath}
								class="shrink-0 text-[var(--color-graphite)] hover:text-[var(--color-ink)] transition-colors"
								aria-label="Copy path"
							>
								{#if copied}
									<Check size={14} />
								{:else}
									<Copy size={14} />
								{/if}
							</button>
						</div>
						<button
							onclick={reset}
							class="text-xs text-[var(--color-slate)] hover:text-[var(--color-ink)] transition-colors text-left"
						>
							Upload another
						</button>
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}
```

- [ ] **Step 2: Typecheck**

```bash
cd ui && pnpm check
```

Expected: no type errors

---

## Task 9: Upload trigger + barrel exports

**Files:**
- Create: `ui/src/lib/uploads/components/upload-trigger.svelte`
- Create: `ui/src/lib/uploads/index.ts`

- [ ] **Step 1: Create the trigger button**

```svelte
<!-- ui/src/lib/uploads/components/upload-trigger.svelte -->
<script lang="ts">
	import { Upload } from '$lib/icons';
	import { uploadState } from '../state.svelte';
</script>

<button
	onclick={() => uploadState.show()}
	class="flex items-center gap-2 px-2.5 py-1.5 text-[12px] text-[var(--color-slate)] hover:bg-[var(--color-paper)]/60 rounded w-full"
	aria-label="Upload screenshot"
>
	<Upload size={14} weight="regular" />
	<span>Screenshot</span>
</button>
```

- [ ] **Step 2: Create the barrel**

```typescript
// ui/src/lib/uploads/index.ts
export { default as UploadModal } from './components/upload-modal.svelte';
export { default as UploadTrigger } from './components/upload-trigger.svelte';
export { uploadState } from './state.svelte';
```

- [ ] **Step 3: Typecheck**

```bash
cd ui && pnpm check
```

Expected: no type errors

- [ ] **Step 4: Commit**

```bash
git add ui/src/lib/uploads/
git commit -m "feat: add upload modal, trigger, and state store"
```

---

## Task 10: Sidebar integration

**Files:**
- Modify: `ui/src/lib/chrome/components/sidebar.svelte`

- [ ] **Step 1: Add the trigger to the sidebar footer**

In `sidebar.svelte`, add the import at the top of the `<script>` block:

```typescript
	import { UploadTrigger } from '$lib/uploads';
```

In the `<!-- Footer -->` section, add `<UploadTrigger />` immediately before the `<a href="/settings">` link:

```svelte
	<div class="mt-auto pt-2.5 border-t border-[var(--color-border)]">
		<UploadTrigger />
		<a
			href="/settings"
			...
```

- [ ] **Step 2: Typecheck**

```bash
cd ui && pnpm check
```

Expected: no type errors

- [ ] **Step 3: Commit**

```bash
git add ui/src/lib/chrome/components/sidebar.svelte
git commit -m "feat: add screenshot upload trigger to sidebar footer"
```

---

## Task 11: App shell — global drag handler + render modal

**Files:**
- Modify: `ui/src/lib/chrome/views/app-shell.svelte`

- [ ] **Step 1: Add the global drag handler and modal render**

Replace the entire `app-shell.svelte` with:

```svelte
<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import Sidebar from '../components/sidebar.svelte';
	import BreadcrumbStrip from '../components/breadcrumb-strip.svelte';
	import { chromeState } from '../state/chrome.state.svelte';
	import { PaletteOverlay, mountPaletteKeybinding } from '$lib/palette';
	import { MOCK_RESULTS } from '$lib/palette/_stories/mock-data';
	import { UploadModal, uploadState } from '$lib/uploads';

	interface ChromeCounts {
		threadCount?: number;
		tasksActive?: number;
	}

	interface Props {
		children: Snippet;
		chrome?: ChromeCounts;
	}

	let { children, chrome = {} }: Props = $props();

	const path = $derived(page.url?.pathname ?? '/');
	const activeSpine = $derived(chromeState.spineFor(path));
	const trail = $derived(chromeState.breadcrumbFor(path));

	// Track drag depth so entering/leaving child elements doesn't flicker the modal
	let dragDepth = $state(0);

	function onDragenter(e: DragEvent) {
		if (e.dataTransfer?.types.includes('Files')) {
			dragDepth++;
			if (dragDepth === 1) uploadState.show();
		}
	}

	function onDragleave() {
		if (dragDepth > 0) dragDepth--;
	}

	function onDrop(e: DragEvent) {
		// Prevent browser from navigating to a dropped file.
		// The modal or its scrim handles the actual file — this is a safety net.
		e.preventDefault();
		dragDepth = 0;
	}

	$effect(() => {
		const off = mountPaletteKeybinding();
		document.addEventListener('dragenter', onDragenter);
		document.addEventListener('dragleave', onDragleave);
		document.addEventListener('drop', onDrop);
		return () => {
			off();
			document.removeEventListener('dragenter', onDragenter);
			document.removeEventListener('dragleave', onDragleave);
			document.removeEventListener('drop', onDrop);
		};
	});
</script>

<div class="flex min-h-screen bg-[var(--color-paper)]">
	<Sidebar
		active={activeSpine}
		threadCount={chrome.threadCount ?? 0}
		tasksActive={chrome.tasksActive ?? 0}
	/>
	<main class="flex-1 flex flex-col min-w-0">
		<BreadcrumbStrip {trail} />
		<div class="flex-1">
			{@render children()}
		</div>
	</main>
</div>

<PaletteOverlay results={MOCK_RESULTS} />
<UploadModal />
```

- [ ] **Step 2: Typecheck**

```bash
cd ui && pnpm check
```

Expected: no type errors

- [ ] **Step 3: Manual verification**

Start the dev server:

```bash
cd ui && pnpm dev
```

Open http://localhost:5180 in a browser. Verify:
1. Sidebar footer shows a "Screenshot" button with an upload icon
2. Clicking it opens the modal with a drop zone
3. Clicking outside the modal (scrim) closes it
4. Dragging any file over the browser window opens the modal automatically
5. Dropping a PNG onto the drop zone shows the uploading spinner, then the path
6. The copy button copies the path to clipboard
7. "Upload another" resets to idle state

- [ ] **Step 4: Commit**

```bash
git add ui/src/lib/chrome/views/app-shell.svelte
git commit -m "feat: global drag-to-open upload modal in app shell"
```

---

## Task 12: End-to-end smoke test

- [ ] **Step 1: Run all backend tests**

```bash
uv run pytest -q
```

Expected: all tests PASS, no regressions

- [ ] **Step 2: Run frontend typecheck**

```bash
cd ui && pnpm check
```

Expected: no errors

- [ ] **Step 3: Manual end-to-end (with real backend)**

```bash
# Terminal 1
uv run forge

# Terminal 2 — upload a test file
curl -s -X POST http://localhost:7030/api/uploads \
  -F "file=@/path/to/any/image.png" | python3 -m json.tool

# Check latest
curl -s http://localhost:7030/api/uploads/latest | python3 -m json.tool
```

Expected: both endpoints return `{ "path": "...", "filename": "screenshot-..." }` and the file exists at the returned path.

- [ ] **Step 4: Final commit if any loose ends**

```bash
git add -p
git commit -m "chore: finalize screenshot upload feature"
```
