# UI Dev-Platform Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the SvelteKit UI in line with the developer-toolbox direction — remove dead personal-assistant code and add four dev-platform surfaces (Repos, Workspaces, Notebook, rewired Today), full-stack.

**Architecture:** Vertical slices delivered in order (Cleanup → Repos → Workspaces → Notebook → Today). Each slice ships backend + UI together. Backend is FastAPI + async SQLite; UI is SvelteKit 2 / Svelte 5 with a zod-validated typed API client (`ui/src/lib/api/typed.ts`). New top-level routes get their own `lib/<feature>` module.

**Tech Stack:** Python 3.13 (uv, pytest, pytest-asyncio, respx), FastAPI; Node 22 (pnpm), SvelteKit, Svelte 5 runes, Tailwind 4, zod, Storybook, Playwright.

**Spec:** `docs/superpowers/specs/2026-05-20-ui-dev-platform-alignment-design.md`

**Conventions for every slice:**
- Run backend tests with `uv run pytest -q`; frontend checks with `cd ui && pnpm check && pnpm build`.
- Commit at the end of each task with the message shown.
- Tests live under `tests/` (backend) and beside components / in `*.test.ts` (frontend).

---

## File Structure

**Slice 0 — Cleanup (deletions):**
- Delete: `forge/api/fields.py`, `forge/api/todos.py`
- Delete: `ui/src/lib/widgets/purchases/`, `ui/src/lib/widgets/workouts/`, `ui/src/lib/widgets/places-map/`
- Delete: `ui/src/lib/schemas/widgets/purchases.ts`, `workouts.ts`, `places-map.ts`
- Delete: `ui/src/lib/fields/` (whole module), `ui/src/lib/library/views/fields-index.svelte`, `ui/src/lib/library/components/field-card.svelte`, `ui/src/lib/library/components/fields-grid.svelte`
- Delete: `ui/src/lib/schemas/todo.ts`, `ui/src/lib/mocks/todo.ts`, `ui/src/lib/mocks/widgets/workouts.ts`
- Modify: `ui/src/lib/widgets/index.ts`, `ui/src/lib/widgets/kernel/widget-host.svelte`, `ui/src/lib/schemas/widgets/index.ts`, `ui/src/lib/api/typed.ts`

**Slice 1 — Repos:**
- Modify: `forge/repos/models.py` (add fields to `Repo`), `forge/repos/registry.py` (populate them), `forge/api/repos.py` (inject tailnet host)
- Create: `forge/tailscale/hostname.py` (resolve tailnet DNS name)
- Create: `tests/test_repos_api.py`
- Create: `ui/src/routes/repos/+page.svelte`, `ui/src/routes/repos/+page.ts`, `ui/src/lib/repos/repos-view.svelte`, `ui/src/lib/repos/index.ts`
- Modify: `ui/src/lib/api/typed.ts` (Repo schema), chrome state + sidebar (Slice navigation task), `library-index.svelte` (drop Repos facet)
- Delete: `ui/src/routes/library/repos/`

**Slice 2 — Workspaces:**
- Modify: `forge/zellij/runner.py` (add `list_sessions`)
- Create: `forge/api/workspaces.py`; Modify: `forge/main.py` (register router + wire store/runner)
- Create: `tests/test_workspaces_api.py`
- Create: `ui/src/routes/workspaces/+page.svelte`, `+page.ts`, `ui/src/lib/workspaces/workspaces-view.svelte`, `index.ts`
- Modify: `ui/src/lib/api/typed.ts` (workspaces client)

**Slice 3 — Notebook:**
- Modify: `forge/api/notebook.py` (remove `/counts`)
- Create: `ui/src/routes/notebook/+page.svelte`, `+page.ts`, `ui/src/lib/notebook/notebook-view.svelte`, `index.ts`
- Modify: `ui/src/lib/api/typed.ts` (drop `counts`)

**Slice 4 — Today:**
- Create: `forge/api/speedtest.py`; Modify: `forge/main.py` (register + wire db)
- Create: `tests/test_speedtest_api.py`
- Modify: `ui/src/lib/api/typed.ts` (speedtest + workspaces already added), `ui/src/routes/today/+page.ts`, `ui/src/lib/today/views/today-view.svelte`

**Navigation (done early in Slice 1, used by all later slices):**
- Modify: `ui/src/lib/chrome/state/chrome.state.svelte.ts`, `ui/src/lib/chrome/components/sidebar.svelte`, `ui/src/lib/icons/index.ts`

---

## Slice 0 — Cleanup

### Task 0.1: Delete unregistered backend API modules

**Files:**
- Delete: `forge/api/fields.py`
- Delete: `forge/api/todos.py`

- [ ] **Step 1: Confirm neither is imported anywhere**

Run: `grep -rn "api.fields\|api import.*fields\|api.todos\|api import.*todos\| fields,\| todos," forge/ | grep -v __pycache__`
Expected: no matches referencing these modules in `forge/main.py` or elsewhere (they were never registered).

- [ ] **Step 2: Delete the files**

```bash
git rm forge/api/fields.py forge/api/todos.py
```

- [ ] **Step 3: Verify backend still imports and tests pass**

Run: `uv run python -c "from forge.main import create_app; create_app()" && uv run pytest -q`
Expected: app constructs, tests pass.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Remove unregistered fields/todos API modules"
```

### Task 0.2: Remove stale widgets (purchases, workouts, places-map)

**Files:**
- Delete: `ui/src/lib/widgets/purchases/`, `ui/src/lib/widgets/workouts/`, `ui/src/lib/widgets/places-map/`
- Delete: `ui/src/lib/schemas/widgets/purchases.ts`, `workouts.ts`, `places-map.ts`
- Delete: `ui/src/lib/mocks/widgets/workouts.ts`
- Modify: `ui/src/lib/widgets/index.ts`, `ui/src/lib/widgets/kernel/widget-host.svelte`, `ui/src/lib/schemas/widgets/index.ts`

- [ ] **Step 1: Delete widget dirs, schemas, and mock**

```bash
git rm -r ui/src/lib/widgets/purchases ui/src/lib/widgets/workouts ui/src/lib/widgets/places-map
git rm ui/src/lib/schemas/widgets/purchases.ts ui/src/lib/schemas/widgets/workouts.ts ui/src/lib/schemas/widgets/places-map.ts
git rm ui/src/lib/mocks/widgets/workouts.ts
```

- [ ] **Step 2: Update `ui/src/lib/widgets/index.ts`**

Remove the three export lines. Resulting file:

```ts
export { default as WidgetShell } from './components/widget-shell.svelte';
export { default as WidgetHost } from './kernel/widget-host.svelte';
export { default as CodeDiff } from './code-diff/code-diff.svelte';
export { default as Weather } from './weather/weather.svelte';
export { default as Result } from './result/result.svelte';
export { default as CodeResult } from './code-result/code-result.svelte';
```

- [ ] **Step 3: Update `ui/src/lib/schemas/widgets/index.ts`**

Replace the whole file with:

```ts
import { z } from 'zod';
import { CodeDiffPayload } from './code-diff';
import { WeatherPayload } from './weather';
import { ResultPayload } from './result';
import { CodeResultPayload } from './code-result';

export * from './code-diff';
export * from './weather';
export * from './result';
export * from './code-result';

/**
 * Discriminated union of every widget payload the assistant can emit.
 * Add new widget schemas here so `widget-host` stays exhaustive.
 */
export const WidgetPayload = z.discriminatedUnion('tool', [
	CodeDiffPayload,
	WeatherPayload,
	ResultPayload,
	CodeResultPayload
]);
export type WidgetPayload = z.infer<typeof WidgetPayload>;
```

- [ ] **Step 4: Update `ui/src/lib/widgets/kernel/widget-host.svelte`**

Remove the imports for `Purchases`, `Workouts`, `PlacesMap` and their `{:else if}` branches. The script imports become:

```svelte
	import CodeDiff from '../code-diff/code-diff.svelte';
	import Weather from '../weather/weather.svelte';
	import Result from '../result/result.svelte';
	import CodeResult from '../code-result/code-result.svelte';
```

And the template becomes:

```svelte
{#if payload.tool === 'code.diff'}
	<CodeDiff {payload} />
{:else if payload.tool === 'weather.forecast'}
	<Weather {payload} />
{:else if payload.tool === 'result'}
	<Result {payload} />
{:else if payload.tool === 'code.result'}
	<CodeResult {payload} />
{:else}
	<div class="font-mono text-[11px] text-[var(--color-warn)]">
		unknown tool: {(payload as { tool: string }).tool}
	</div>
{/if}
```

- [ ] **Step 5: Find and remove any remaining references (stories, mock-data)**

Run: `grep -rln "Purchases\|Workouts\|PlacesMap\|finance.purchases\|health.workouts\|places.map\|purchases\|workouts\|places-map" ui/src --include=*.ts --include=*.svelte | grep -v node_modules`
For each hit (e.g. `_stories` files, `lib/palette/_stories/mock-data.ts`), remove the offending entries. If a `*.stories.ts` exists only for a deleted widget, `git rm` it.

- [ ] **Step 6: Verify typecheck + build pass**

Run: `cd ui && pnpm check && pnpm build`
Expected: no type errors, build succeeds.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Remove stale personal-assistant widgets (purchases, workouts, places-map)"
```

### Task 0.3: Remove the fields UI module and todos/fields API clients

**Files:**
- Delete: `ui/src/lib/fields/`, `ui/src/lib/library/views/fields-index.svelte`, `ui/src/lib/library/components/field-card.svelte`, `ui/src/lib/library/components/fields-grid.svelte`
- Delete: `ui/src/lib/schemas/todo.ts`, `ui/src/lib/mocks/todo.ts`
- Modify: `ui/src/lib/api/typed.ts`

- [ ] **Step 1: Delete the fields module and field library views**

```bash
git rm -r ui/src/lib/fields
git rm ui/src/lib/library/views/fields-index.svelte ui/src/lib/library/components/field-card.svelte ui/src/lib/library/components/fields-grid.svelte
git rm ui/src/lib/schemas/todo.ts ui/src/lib/mocks/todo.ts
```

- [ ] **Step 2: Edit `ui/src/lib/api/typed.ts` — remove Todo import and Field/Todo schemas**

Remove line `import { Todo } from '$lib/schemas/todo';` (line 15).
Remove the `FieldStatus`, `FieldSummary`, `FieldList`, `FieldEntries` schema blocks (lines ~80-100).
Remove the `TodoList` schema (lines ~115-117).
Remove the `export type FieldSummary = ...` export (line ~182).
Remove the `fields: { ... }` client block (lines ~218-222).
Remove the `todos: { ... }` client block (lines ~239-250).

- [ ] **Step 3: Find dangling references to removed exports**

Run: `grep -rln "schemas/todo\|lib/fields\|FieldSummary\|api.fields\|api.todos\|fields-index\|field-card\|fields-grid" ui/src | grep -v node_modules`
For each hit (notably `ui/src/lib/library/index.ts` and any route under `library`), remove the import/usage. Check `ui/src/routes/library/` for a `fields` route — if one exists, `git rm -r` it.

- [ ] **Step 4: Verify typecheck + build pass**

Run: `cd ui && pnpm check && pnpm build`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "Remove fields UI module and fields/todos API clients"
```

---

## Slice 1 — Repos (enrich + promote to /repos)

### Task 1.1: Navigation — 7-item spine

**Files:**
- Modify: `ui/src/lib/chrome/state/chrome.state.svelte.ts`
- Modify: `ui/src/lib/chrome/components/sidebar.svelte`
- Modify: `ui/src/lib/icons/index.ts`

- [ ] **Step 1: Add icons in `ui/src/lib/icons/index.ts`**

Add `Stack`, `Package`, `Notebook` to the export block (all valid phosphor-svelte names). `ListChecks` is **already exported** — do NOT add it again (duplicate exports fail the build). Add the three new names to the `// Spine` group:

```ts
	// Spine
	Sun,
	ChatCircle,
	Books,
	Robot,
	Stack,
	Package,
	Notebook,
```

Verify with `grep -n "ListChecks\|Stack\|Package\|Notebook" ui/src/lib/icons/index.ts` that each appears exactly once.

- [ ] **Step 2: Update the `Spine` type and `spineFromPath` in `chrome.state.svelte.ts`**

```ts
export type Spine = 'today' | 'threads' | 'workspaces' | 'repos' | 'tasks' | 'notebook' | 'library';

const spineFromPath = (path: string): Spine | null => {
	if (path.startsWith('/today')) return 'today';
	if (path.startsWith('/threads')) return 'threads';
	if (path.startsWith('/workspaces')) return 'workspaces';
	if (path.startsWith('/repos')) return 'repos';
	if (path.startsWith('/tasks')) return 'tasks';
	if (path.startsWith('/notebook')) return 'notebook';
	if (path.startsWith('/library')) return 'library';
	return null;
};
```

- [ ] **Step 3: Update the spine in `sidebar.svelte`**

Update the icon import to include the new icons:

```svelte
	import { Sun, ChatCircle, Books, ListChecks, Gear, Stack, Package, Notebook } from '$lib/icons';
```

Replace the spine block (the four existing `<SpineItem>`s) with seven items in order. Insert Workspaces + Repos between Threads and Tasks, and Notebook between Tasks and Library:

```svelte
	<SpineItem href="/today" label="Today" icon={Sun} active={active === 'today'}>
		{#snippet meta()}<Meta size="xs">{todayDow}</Meta>{/snippet}
	</SpineItem>
	<SpineItem href="/threads" label="Threads" icon={ChatCircle} active={active === 'threads'}>
		{#snippet meta()}<Meta size="xs">{threadCount || ''}</Meta>{/snippet}
	</SpineItem>
	<SpineItem href="/workspaces" label="Workspaces" icon={Stack} active={active === 'workspaces'} />
	<SpineItem href="/repos" label="Repos" icon={Package} active={active === 'repos'} />
	<SpineItem href="/tasks" label="Tasks" icon={ListChecks} active={active === 'tasks'}>
		{#snippet meta()}
			{#if tasksActive > 0}
				<span class="inline-flex items-center gap-1">
					<StatusDot tone="moss" />
					<Meta size="xs">{tasksActive}</Meta>
				</span>
			{/if}
		{/snippet}
	</SpineItem>
	<SpineItem href="/notebook" label="Notebook" icon={Notebook} active={active === 'notebook'} />
	<SpineItem href="/library" label="Library" icon={Books} active={active === 'library'}>
		{#snippet meta()}<Meta size="xs">{libraryCount ? libraryCount.toLocaleString() : ''}</Meta>{/snippet}
	</SpineItem>
```

(Verify `SpineItem` renders fine without a `meta` snippet — `spine-item.svelte` uses an optional snippet. If it requires one, pass `{#snippet meta()}<Meta size="xs"></Meta>{/snippet}`.)

- [ ] **Step 4: Verify typecheck + build, then manually confirm the sidebar**

Run: `cd ui && pnpm check && pnpm build`
Expected: clean. Then run `pnpm dev` and confirm the sidebar shows seven items and the active state highlights correctly when navigating to `/workspaces`, `/repos`, `/notebook` (these will 404 until later tasks — that's expected; just confirm the spine renders and highlights).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "Add Workspaces/Repos/Notebook to the sidebar spine"
```

### Task 1.2: Backend — resolve tailnet hostname

**Files:**
- Create: `forge/tailscale/hostname.py`
- Test: `tests/test_tailscale_hostname.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tailscale_hostname.py
import json
from forge.tailscale.hostname import parse_tailnet_dns_name


def test_parse_tailnet_dns_name_strips_trailing_dot():
    status = {"Self": {"DNSName": "ardent-forge.feist-gondola.ts.net."}}
    assert parse_tailnet_dns_name(json.dumps(status)) == "ardent-forge.feist-gondola.ts.net"


def test_parse_tailnet_dns_name_missing_returns_none():
    assert parse_tailnet_dns_name(json.dumps({"Self": {}})) is None
    assert parse_tailnet_dns_name("not json") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tailscale_hostname.py -v`
Expected: FAIL with `ModuleNotFoundError: forge.tailscale.hostname`.

- [ ] **Step 3: Write `forge/tailscale/hostname.py`**

```python
"""Resolve the tailnet DNS name of this machine for building dev-server URLs."""
import asyncio
import json
import logging
import shutil

logger = logging.getLogger(__name__)


def parse_tailnet_dns_name(status_json: str) -> str | None:
    """Extract Self.DNSName (trailing dot stripped) from `tailscale status --json`."""
    try:
        data = json.loads(status_json)
    except (json.JSONDecodeError, TypeError):
        return None
    name = (data.get("Self") or {}).get("DNSName")
    if not name:
        return None
    return name.rstrip(".")


async def resolve_tailnet_host() -> str | None:
    """Return this machine's tailnet DNS name, or None if tailscale is unavailable."""
    if shutil.which("tailscale") is None:
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            "tailscale", "status", "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return None
        return parse_tailnet_dns_name(stdout.decode())
    except Exception:
        logger.warning("Failed to resolve tailnet host", exc_info=True)
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tailscale_hostname.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/tailscale/hostname.py tests/test_tailscale_hostname.py
git commit -m "Add tailnet hostname resolver for dev-server URLs"
```

### Task 1.3: Backend — enrich the Repo model and API

**Files:**
- Modify: `forge/repos/models.py`, `forge/repos/registry.py`, `forge/api/repos.py`, `forge/main.py`
- Test: `tests/test_repos_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_repos_api.py
import pytest
from httpx import AsyncClient, ASGITransport

from forge.main import create_app
from forge.repos import RepoRegistry
from forge.repos.models import Repo
from forge.api import repos as repos_api


def _make_repo(**kw):
    base = dict(name="acme", path="/home/u/Repos/acme", default_branch="main",
                dev_port=5180, claude_label="claude", env_keys=["TOKEN"])
    base.update(kw)
    return Repo(**base)


@pytest.fixture
def client():
    app = create_app()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_repo_api_exposes_dev_url_and_env_keys(client):
    reg = RepoRegistry("/tmp/nonexistent")
    reg._repos = {"acme": _make_repo()}
    reg._tailnet_host = "box.example.ts.net"
    repos_api.set_registry(reg)

    resp = await client.get("/api/repos")
    assert resp.status_code == 200
    body = resp.json()
    repo = body[0]
    assert repo["claude_label"] == "claude"
    assert repo["env_keys"] == ["TOKEN"]
    assert repo["dev_url"] == "https://box.example.ts.net:5180/"


async def test_repo_dev_url_none_without_port_or_host(client):
    reg = RepoRegistry("/tmp/nonexistent")
    reg._repos = {"acme": _make_repo(dev_port=None)}
    reg._tailnet_host = "box.example.ts.net"
    repos_api.set_registry(reg)

    resp = await client.get("/api/repos")
    assert resp.json()[0]["dev_url"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_repos_api.py -v`
Expected: FAIL — `Repo` has no `claude_label`/`env_keys`/`dev_url`.

- [ ] **Step 3: Extend the `Repo` model in `forge/repos/models.py`**

Replace the `Repo` class with:

```python
class Repo(BaseModel):
    name: str
    path: str
    default_branch: str
    dev_port: int | None = None
    claude_label: str | None = None
    # Names of env vars declared in repo.yaml. VALUES ARE NEVER EXPOSED — they
    # may hold op:// secret references.
    env_keys: list[str] = []
    # Computed Tailscale dev-server URL; None when no dev_port or tailscale is down.
    dev_url: str | None = None
```

- [ ] **Step 4: Populate the new fields in `forge/repos/registry.py`**

Add a `_tailnet_host` attribute and a setter, build `dev_url` in `_load_repo`, and populate `claude_label`/`env_keys`:

In `__init__`, add:

```python
        self._tailnet_host: str | None = None
```

Add a method on `RepoRegistry`:

```python
    def set_tailnet_host(self, host: str | None) -> None:
        self._tailnet_host = host
        # Recompute dev_url for already-scanned repos.
        for repo in self._repos.values():
            repo.dev_url = self._dev_url(repo.dev_port)

    def _dev_url(self, dev_port: int | None) -> str | None:
        if dev_port is None or not self._tailnet_host:
            return None
        return f"https://{self._tailnet_host}:{dev_port}/"
```

Replace `_load_repo` with:

```python
    async def _load_repo(self, path: Path) -> Repo:
        default_branch = await self._get_default_branch(path)
        config = self._load_config(path)
        dev_port = config.dev_port if config else None
        return Repo(
            name=path.name,
            path=str(path),
            default_branch=default_branch,
            dev_port=dev_port,
            claude_label=config.claude_label if config else None,
            env_keys=list(config.env.keys()) if config else [],
            dev_url=self._dev_url(dev_port),
        )
```

- [ ] **Step 5: Wire the tailnet host at startup in `forge/main.py`**

After the repo registry is scanned (right after `repos_api.set_registry(repo_registry)`), add:

```python
        from forge.tailscale.hostname import resolve_tailnet_host
        repo_registry.set_tailnet_host(await resolve_tailnet_host())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_repos_api.py -v`
Expected: PASS (both tests).

- [ ] **Step 7: Run the full backend suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add forge/repos/models.py forge/repos/registry.py forge/api/repos.py forge/main.py tests/test_repos_api.py
git commit -m "Enrich repos API with dev_url, claude_label, env_keys"
```

### Task 1.4: Frontend — Repos page at /repos

**Files:**
- Modify: `ui/src/lib/api/typed.ts` (Repo schema)
- Create: `ui/src/lib/repos/repos-view.svelte`, `ui/src/lib/repos/index.ts`, `ui/src/routes/repos/+page.svelte`, `ui/src/routes/repos/+page.ts`
- Delete: `ui/src/routes/library/repos/`
- Modify: `ui/src/lib/library/views/library-index.svelte` (drop Repos facet)

- [ ] **Step 1: Update the `Repo` zod schema in `ui/src/lib/api/typed.ts`**

```ts
const Repo = z.object({
	name: z.string(),
	path: z.string(),
	default_branch: z.string(),
	dev_port: z.number().nullable().optional(),
	claude_label: z.string().nullable().optional(),
	env_keys: z.array(z.string()).optional(),
	dev_url: z.string().nullable().optional()
});
```

- [ ] **Step 2: Create `ui/src/lib/repos/repos-view.svelte`**

```svelte
<script lang="ts">
	import { Display, Heading, Eyebrow, Body, Meta } from '$lib/typography';
	import { Card, Chip } from '$lib/components';
	import type { Repo } from '$lib/api/typed';

	interface Props { repos?: Repo[]; }
	let { repos = [] }: Props = $props();
</script>

<div class="flex flex-col gap-8 px-14 py-9 max-w-[1200px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>REPOS</Eyebrow>
		<Display size="lg">Repos</Display>
		<Heading size="sm" italic>Git repositories scanned from the workspace.</Heading>
	</div>

	{#if repos.length === 0}
		<Body muted>No repositories found. Add repos to ~/Repos and restart Forge.</Body>
	{:else}
		<div class="grid grid-cols-2 gap-4">
			{#each repos as repo (repo.name)}
				<Card surface="paper" class="p-5">
					<div class="flex flex-col gap-2">
						<div class="flex items-center justify-between gap-2">
							<Heading size="sm">{repo.name}</Heading>
							{#if repo.claude_label}<Chip tone="moss">{repo.claude_label}</Chip>{/if}
						</div>
						<div class="flex flex-col gap-0.5">
							<Meta size="xs">branch: {repo.default_branch}</Meta>
							<Meta size="xs">{repo.path}</Meta>
							{#if repo.env_keys && repo.env_keys.length > 0}
								<Meta size="xs">env: {repo.env_keys.join(', ')}</Meta>
							{/if}
						</div>
						{#if repo.dev_url}
							<a href={repo.dev_url} target="_blank" rel="noreferrer"
							   class="text-[12px] text-[var(--color-moss)] hover:underline">
								dev server :{repo.dev_port} ↗
							</a>
						{/if}
					</div>
				</Card>
			{/each}
		</div>
	{/if}
</div>
```

- [ ] **Step 3: Create `ui/src/lib/repos/index.ts`**

```ts
export { default as ReposView } from './repos-view.svelte';
```

- [ ] **Step 4: Create `ui/src/routes/repos/+page.ts`**

```ts
import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;

export const load: PageLoad = async () => {
	const repos = await api.repos.list().catch(() => []);
	return { repos };
};
```

- [ ] **Step 5: Create `ui/src/routes/repos/+page.svelte`**

```svelte
<script lang="ts">
	import { ReposView } from '$lib/repos';
	import type { PageData } from './$types';
	interface Props { data: PageData; }
	let { data }: Props = $props();
</script>

<ReposView repos={data.repos} />
```

- [ ] **Step 6: Remove the old library repos route and the Library "Repos" facet**

```bash
git rm -r ui/src/routes/library/repos
```

In `ui/src/lib/library/views/library-index.svelte`, delete the `Repos` facet object from the `facets` array (the block with `label: 'Repos'`), and remove the now-unused `repoCount` prop usage (leave the prop in place to avoid churn elsewhere, or remove it from both this file and `ui/src/routes/library/+page.svelte` + `+page.ts` if trivially traceable).

- [ ] **Step 7: Verify typecheck + build, then test in browser**

Run: `cd ui && pnpm check && pnpm build`
Expected: clean. Then `pnpm dev` (with backend running via `uv run forge`) and confirm `/repos` lists repos, dev-server links open the Tailscale URL in a new tab, and the Library page no longer shows Repos.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "Add top-level Repos page; remove repos from Library"
```

---

## Slice 2 — Workspaces (live Zellij sessions)

### Task 2.1: Backend — list_sessions on ZellijRunner

**Files:**
- Modify: `forge/zellij/runner.py`
- Test: `tests/test_zellij_sessions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_zellij_sessions.py
from forge.zellij.runner import parse_session_list


def test_parse_session_list_extracts_names_and_state():
    raw = (
        "agent-01HXYZ [Created 2h ago]\n"
        "agent-01ABCD [Created 5m ago] (EXITED - attach to resurrect)\n"
        "personal [Created 1d ago]\n"
    )
    sessions = parse_session_list(raw)
    assert sessions == [
        {"name": "agent-01HXYZ", "exited": False},
        {"name": "agent-01ABCD", "exited": True},
        {"name": "personal", "exited": False},
    ]


def test_parse_session_list_empty():
    assert parse_session_list("") == []
    assert parse_session_list("No active zellij sessions found.") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_zellij_sessions.py -v`
Expected: FAIL — `parse_session_list` does not exist.

- [ ] **Step 3: Add `parse_session_list` and `list_sessions` to `forge/zellij/runner.py`**

Add a module-level function (above the class):

```python
def parse_session_list(raw: str) -> list[dict]:
    """Parse `zellij list-sessions` output into [{name, exited}].

    Each line looks like: `<name> [Created ...]` optionally followed by
    `(EXITED - ...)`. ANSI codes are tolerated by splitting on the first space.
    """
    import re

    sessions: list[dict] = []
    for line in raw.splitlines():
        line = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
        if not line or line.lower().startswith("no active"):
            continue
        name = line.split()[0]
        sessions.append({"name": name, "exited": "EXITED" in line})
    return sessions
```

Add a method on `ZellijRunner`:

```python
    @classmethod
    async def list_sessions(cls) -> list[dict]:
        """Return live zellij sessions as [{name, exited}]. Empty when unavailable."""
        if not cls.available():
            return []
        proc = await asyncio.create_subprocess_exec(
            "zellij", "list-sessions",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return []
        return parse_session_list(stdout.decode())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_zellij_sessions.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/zellij/runner.py tests/test_zellij_sessions.py
git commit -m "Add zellij list-sessions parsing to ZellijRunner"
```

### Task 2.2: Backend — /api/workspaces endpoint

**Files:**
- Create: `forge/api/workspaces.py`
- Modify: `forge/main.py`
- Test: `tests/test_workspaces_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workspaces_api.py
import pytest
from httpx import AsyncClient, ASGITransport

from forge.main import create_app
from forge.api import workspaces as workspaces_api


class _FakeStore:
    def __init__(self, tasks):
        self._tasks = {t["id"]: t for t in tasks}

    async def get(self, task_id):
        t = self._tasks.get(task_id)
        if t is None:
            return None
        return type("T", (), t)


@pytest.fixture
def client():
    app = create_app()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_workspaces_joins_sessions_to_tasks(client, monkeypatch):
    async def fake_list_sessions():
        return [{"name": "agent-01HX", "exited": False}, {"name": "personal", "exited": False}]

    monkeypatch.setattr(workspaces_api, "_list_sessions", fake_list_sessions)
    store = _FakeStore([
        {"id": "01HX", "title": "Fix login", "repo": "acme", "status": "executing"},
    ])
    workspaces_api.set_store(store)

    resp = await client.get("/api/workspaces")
    assert resp.status_code == 200
    body = resp.json()
    # Only agent- sessions are workspaces; 'personal' is ignored.
    assert len(body) == 1
    ws = body[0]
    assert ws["session"] == "agent-01HX"
    assert ws["task_id"] == "01HX"
    assert ws["title"] == "Fix login"
    assert ws["repo"] == "acme"
    assert ws["status"] == "executing"
    assert ws["attach_cmd"] == "ssh box -t zellij attach agent-01HX"
    assert ws["exited"] is False


async def test_workspaces_unknown_task_still_listed(client, monkeypatch):
    async def fake_list_sessions():
        return [{"name": "agent-09ZZ", "exited": True}]

    monkeypatch.setattr(workspaces_api, "_list_sessions", fake_list_sessions)
    workspaces_api.set_store(_FakeStore([]))

    resp = await client.get("/api/workspaces")
    body = resp.json()
    assert body[0]["task_id"] == "09ZZ"
    assert body[0]["title"] is None
    assert body[0]["exited"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workspaces_api.py -v`
Expected: FAIL — `forge.api.workspaces` does not exist.

- [ ] **Step 3: Create `forge/api/workspaces.py`**

```python
from fastapi import APIRouter

from forge.zellij.runner import ZellijRunner

router = APIRouter()
_store = None


def set_store(store) -> None:
    global _store
    _store = store


# Indirection so tests can monkeypatch the session source.
async def _list_sessions() -> list[dict]:
    return await ZellijRunner.list_sessions()


@router.get("/api/workspaces")
async def list_workspaces() -> list[dict]:
    """Live agent Zellij sessions joined to their tasks.

    Sessions are named ``agent-<task-id>`` by the Code agent. Non-agent
    sessions are ignored. A session whose task is gone is still listed.
    """
    sessions = await _list_sessions()
    out: list[dict] = []
    for s in sessions:
        name = s["name"]
        if not name.startswith("agent-"):
            continue
        task_id = name[len("agent-"):]
        task = await _store.get(task_id) if _store is not None else None
        status = getattr(task, "status", None) if task else None
        out.append({
            "session": name,
            "task_id": task_id,
            "title": getattr(task, "title", None) if task else None,
            "repo": getattr(task, "repo", None) if task else None,
            # status may be a StrEnum on the real Task; str() handles both.
            "status": str(status) if status is not None else None,
            "attach_cmd": f"ssh box -t zellij attach {name}",
            "exited": s["exited"],
        })
    return out
```

- [ ] **Step 4: Register the router and wire the store in `forge/main.py`**

Add to the `from forge.api import (...)` block: `workspaces as workspaces_api,`.
Add in `create_app`: `app.include_router(workspaces_api.router)`.
In the lifespan, after `tasks.set_store(store)` (the one near `app.state.connectors`), add: `workspaces_api.set_store(store)`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_workspaces_api.py -v`
Expected: PASS (both).

- [ ] **Step 6: Full suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add forge/api/workspaces.py forge/main.py tests/test_workspaces_api.py
git commit -m "Add /api/workspaces endpoint listing live Zellij sessions"
```

### Task 2.3: Frontend — Workspaces page at /workspaces

**Files:**
- Modify: `ui/src/lib/api/typed.ts`
- Create: `ui/src/lib/workspaces/workspaces-view.svelte`, `index.ts`, `ui/src/routes/workspaces/+page.svelte`, `+page.ts`

- [ ] **Step 1: Add the workspaces client to `ui/src/lib/api/typed.ts`**

Add a schema near the other schemas:

```ts
const Workspace = z.object({
	session: z.string(),
	task_id: z.string(),
	title: z.string().nullable().optional(),
	repo: z.string().nullable().optional(),
	status: z.string().nullable().optional(),
	attach_cmd: z.string(),
	exited: z.boolean()
});
const WorkspaceList = z.array(Workspace);
export type Workspace = z.infer<typeof Workspace>;
```

Add a client block in the `api` object (after `repos`):

```ts
	workspaces: {
		list: () => request('/api/workspaces', WorkspaceList)
	},
```

- [ ] **Step 2: Create `ui/src/lib/workspaces/workspaces-view.svelte`**

```svelte
<script lang="ts">
	import { Display, Heading, Eyebrow, Body, Meta } from '$lib/typography';
	import { Card, Chip, StatusDot } from '$lib/components';
	import type { Workspace } from '$lib/api/typed';

	interface Props { workspaces?: Workspace[]; }
	let { workspaces = [] }: Props = $props();
</script>

<div class="flex flex-col gap-8 px-14 py-9 max-w-[1200px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>WORKSPACES</Eyebrow>
		<Display size="lg">Workspaces</Display>
		<Heading size="sm" italic>Live development sessions running on the box.</Heading>
	</div>

	{#if workspaces.length === 0}
		<Body muted>No live sessions. Dispatch a Code task to start one.</Body>
	{:else}
		<div class="flex flex-col gap-3">
			{#each workspaces as ws (ws.session)}
				<Card surface="paper" class="p-5">
					<div class="flex flex-col gap-2">
						<div class="flex items-center justify-between gap-2">
							<a href={`/tasks/${ws.task_id}`} class="hover:underline">
								<Heading size="sm">{ws.title ?? ws.session}</Heading>
							</a>
							<span class="inline-flex items-center gap-1.5">
								<StatusDot tone={ws.exited ? 'stone' : 'moss'} />
								<Meta size="xs">{ws.exited ? 'exited' : (ws.status ?? 'running')}</Meta>
							</span>
						</div>
						{#if ws.repo}<Chip tone="graphite">{ws.repo}</Chip>{/if}
						<code class="font-mono text-[11px] text-[var(--color-graphite)] select-all">
							{ws.attach_cmd}
						</code>
					</div>
				</Card>
			{/each}
		</div>
	{/if}
</div>
```

(If `StatusDot`/`Chip` aren't exported from `$lib/components`, check `ui/src/lib/components/index.ts` and import from the correct path — they're used in `today-view.svelte` and `sidebar.svelte`.)

- [ ] **Step 3: Create `ui/src/lib/workspaces/index.ts`**

```ts
export { default as WorkspacesView } from './workspaces-view.svelte';
```

- [ ] **Step 4: Create `ui/src/routes/workspaces/+page.ts`**

```ts
import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;

export const load: PageLoad = async () => {
	const workspaces = await api.workspaces.list().catch(() => []);
	return { workspaces };
};
```

- [ ] **Step 5: Create `ui/src/routes/workspaces/+page.svelte`**

```svelte
<script lang="ts">
	import { WorkspacesView } from '$lib/workspaces';
	import type { PageData } from './$types';
	interface Props { data: PageData; }
	let { data }: Props = $props();
</script>

<WorkspacesView workspaces={data.workspaces} />
```

- [ ] **Step 6: Verify typecheck + build, then test in browser**

Run: `cd ui && pnpm check && pnpm build`
Expected: clean. With backend running, confirm `/workspaces` shows the empty state (or live sessions if a Code task is running), and the attach command is selectable; the title links to `/tasks/<id>`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Add Workspaces page listing live dev sessions"
```

---

## Slice 3 — Notebook (read-only browse)

### Task 3.1: Backend — remove the stale /counts endpoint

**Files:**
- Modify: `forge/api/notebook.py`
- Modify: `ui/src/lib/api/typed.ts` (drop `counts`)

- [ ] **Step 1: Confirm nothing backend-side depends on /counts**

Run: `grep -rn "counts\|/counts" forge/ | grep -v __pycache__ | grep -i notebook`
Expected: only the route definition in `forge/api/notebook.py`.

- [ ] **Step 2: Delete the `counts` route from `forge/api/notebook.py`**

Remove the entire `@router.get("/counts")` handler (`async def counts(...)` and its body, including the inner `_count` helper).

- [ ] **Step 3: Remove the `counts` client from `ui/src/lib/api/typed.ts`**

Delete the `counts: () => request('/api/notebook/counts', ...)` line from the `notebook` block (and the trailing comma fix on the preceding `search` entry).

- [ ] **Step 4: Verify backend imports + UI typechecks**

Run: `uv run python -c "from forge.main import create_app; create_app()"` and `cd ui && pnpm check`
Expected: both clean.

- [ ] **Step 5: Commit**

```bash
git add forge/api/notebook.py ui/src/lib/api/typed.ts
git commit -m "Remove stale notebook /counts endpoint and client"
```

### Task 3.2: Frontend — Notebook browser at /notebook

**Files:**
- Create: `ui/src/lib/notebook/notebook-view.svelte`, `index.ts`, `ui/src/routes/notebook/+page.svelte`, `+page.ts`

- [ ] **Step 1: Confirm the notebook API client shape**

The existing `api.notebook` exposes:
- `list(path)` → `{ path, entries: string[] }`
- `read(path)` → `{ path, body }`
- `search(q, path?)` → `{ path, line_number, line }[]`

These are sufficient; no backend change needed for browse.

- [ ] **Step 2: Create `ui/src/lib/notebook/notebook-view.svelte`**

```svelte
<script lang="ts">
	import { Display, Heading, Eyebrow, Body, Meta } from '$lib/typography';
	import { Card } from '$lib/components';
	import { api } from '$lib/api/typed';

	interface Props {
		initialPath?: string;
		initialEntries?: string[];
	}
	let { initialPath = '', initialEntries = [] }: Props = $props();

	let cwd = $state(initialPath);
	let entries = $state<string[]>(initialEntries);
	let body = $state<string | null>(null);
	let query = $state('');
	let results = $state<{ path: string; line_number: number; line: string }[]>([]);

	async function openEntry(name: string) {
		const full = cwd ? `${cwd}/${name}` : name;
		if (name.endsWith('.md')) {
			body = (await api.notebook.read(full)).body;
		} else {
			cwd = full;
			body = null;
			entries = (await api.notebook.list(full)).entries;
		}
	}

	async function goUp() {
		cwd = cwd.includes('/') ? cwd.slice(0, cwd.lastIndexOf('/')) : '';
		body = null;
		entries = (await api.notebook.list(cwd)).entries;
	}

	async function runSearch() {
		if (!query.trim()) { results = []; return; }
		results = await api.notebook.search(query);
	}
</script>

<div class="flex flex-col gap-6 px-14 py-9 max-w-[1100px] mx-auto">
	<div class="flex flex-col gap-1.5">
		<Eyebrow>NOTEBOOK</Eyebrow>
		<Display size="lg">Notebook</Display>
		<Heading size="sm" italic>Read-only reference from the Obsidian vault.</Heading>
	</div>

	<form class="flex gap-2" onsubmit={(e) => { e.preventDefault(); runSearch(); }}>
		<input bind:value={query} placeholder="Search the vault…"
			class="flex-1 px-3 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-paper)]" />
	</form>

	{#if results.length > 0}
		<Card surface="paper" class="p-4">
			<div class="flex flex-col gap-1.5">
				{#each results as r (r.path + r.line_number)}
					<button class="text-left hover:underline" onclick={() => { query=''; results=[]; openEntry(r.path); }}>
						<Meta size="xs">{r.path}:{r.line_number}</Meta>
						<Body size="sm">{r.line}</Body>
					</button>
				{/each}
			</div>
		</Card>
	{/if}

	<div class="flex items-center gap-2">
		<Meta size="xs">/{cwd}</Meta>
		{#if cwd}<button class="text-[12px] hover:underline" onclick={goUp}>↑ up</button>{/if}
	</div>

	{#if body !== null}
		<Card surface="paper" class="p-6">
			<pre class="whitespace-pre-wrap font-mono text-[13px] leading-relaxed">{body}</pre>
		</Card>
	{:else}
		<div class="flex flex-col gap-1">
			{#each entries as name (name)}
				<button class="text-left px-2 py-1.5 hover:bg-[var(--color-bench)] rounded" onclick={() => openEntry(name)}>
					<Body size="sm">{name.endsWith('.md') ? '📄' : '📁'} {name}</Body>
				</button>
			{/each}
		</div>
	{/if}
</div>
```

(Markdown is rendered as preformatted text — keep it simple and read-only. If the project already has a markdown renderer component, use it instead; otherwise `<pre>` is the YAGNI choice.)

- [ ] **Step 3: Create `ui/src/lib/notebook/index.ts`**

```ts
export { default as NotebookView } from './notebook-view.svelte';
```

- [ ] **Step 4: Create `ui/src/routes/notebook/+page.ts`**

```ts
import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;

export const load: PageLoad = async () => {
	const root = await api.notebook.list('').catch(() => ({ path: '', entries: [] as string[] }));
	return { initialPath: root.path, initialEntries: root.entries };
};
```

- [ ] **Step 5: Create `ui/src/routes/notebook/+page.svelte`**

```svelte
<script lang="ts">
	import { NotebookView } from '$lib/notebook';
	import type { PageData } from './$types';
	interface Props { data: PageData; }
	let { data }: Props = $props();
</script>

<NotebookView initialPath={data.initialPath} initialEntries={data.initialEntries} />
```

- [ ] **Step 6: Verify typecheck + build, then test in browser**

Run: `cd ui && pnpm check && pnpm build`
Expected: clean. With backend running and a notebook dir configured, confirm `/notebook` lists the vault, opening a folder drills in, opening a `.md` renders it, `↑ up` works, and search returns hits. If the notebook dir is not configured, confirm the page shows an empty list without crashing.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Add read-only Notebook browser page"
```

---

## Slice 4 — Today (rewire dashboard)

### Task 4.1: Backend — /api/speedtest/latest

**Files:**
- Create: `forge/api/speedtest.py`
- Modify: `forge/main.py`
- Test: `tests/test_speedtest_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_speedtest_api.py
import pytest
from httpx import AsyncClient, ASGITransport

from forge.main import create_app
from forge.api import speedtest as speedtest_api


class _FakeDB:
    def __init__(self, row):
        self._row = row

    async def fetch_one(self, sql, params=()):
        return self._row


@pytest.fixture
def client():
    app = create_app()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_speedtest_latest_returns_row(client):
    speedtest_api.set_db(_FakeDB({
        "id": "01", "download_mbps": 512.0, "upload_mbps": 48.0,
        "ping_ms": 9.0, "server_name": "X", "server_location": "Y",
        "tested_at": "2026-05-20T00:00:00+00:00",
    }))
    resp = await client.get("/api/speedtest/latest")
    assert resp.status_code == 200
    assert resp.json()["download_mbps"] == 512.0


async def test_speedtest_latest_empty(client):
    speedtest_api.set_db(_FakeDB(None))
    resp = await client.get("/api/speedtest/latest")
    assert resp.status_code == 200
    assert resp.json() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_speedtest_api.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Create `forge/api/speedtest.py`**

```python
from fastapi import APIRouter

router = APIRouter()
_db = None


def set_db(db) -> None:
    global _db
    _db = db


@router.get("/api/speedtest/latest")
async def latest() -> dict | None:
    """Most recent speed test result, or null if none recorded."""
    if _db is None:
        return None
    return await _db.fetch_one(
        "SELECT * FROM speedtest_results ORDER BY tested_at DESC LIMIT 1"
    )
```

- [ ] **Step 4: Register and wire in `forge/main.py`**

Add to the API import block: `speedtest as speedtest_api,`.
Add in `create_app`: `app.include_router(speedtest_api.router)`.
In the lifespan, after the db is initialized (near `store = TaskStore(db)`), add: `speedtest_api.set_db(db)`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_speedtest_api.py -v`
Expected: PASS (both).

- [ ] **Step 6: Full suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add forge/api/speedtest.py forge/main.py tests/test_speedtest_api.py
git commit -m "Add /api/speedtest/latest endpoint"
```

### Task 4.2: Frontend — rewire the Today dashboard

**Files:**
- Modify: `ui/src/lib/api/typed.ts` (speedtest client)
- Modify: `ui/src/routes/today/+page.ts`
- Modify: `ui/src/lib/today/views/today-view.svelte`

- [ ] **Step 1: Add the speedtest client to `ui/src/lib/api/typed.ts`**

```ts
const Speedtest = z.object({
	download_mbps: z.number(),
	upload_mbps: z.number(),
	ping_ms: z.number(),
	tested_at: z.string()
}).passthrough().nullable();
export type Speedtest = z.infer<typeof Speedtest>;
```

Add a client block:

```ts
	speedtest: {
		latest: () => request('/api/speedtest/latest', Speedtest)
	},
```

- [ ] **Step 2: Update `ui/src/routes/today/+page.ts`**

Replace the loader with one that also pulls workspaces + speedtest and a dev-servers list:

```ts
import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';
import { adaptThread, adaptTaskToAgentRun } from '$lib/api/adapters';

export const ssr = false;

export const load: PageLoad = async () => {
	const [threads, tasks, repos, weather, workspaces, speedtest] = await Promise.all([
		api.threads.list().then((raw) => raw.map((t) => adaptThread(t))).catch(() => []),
		api.tasks.list().catch(() => []),
		api.repos.list().catch(() => []),
		api.weather.current().catch(() => null),
		api.workspaces.list().catch(() => []),
		api.speedtest.latest().catch(() => null)
	]);

	const activeTasks = tasks.filter((t) =>
		['executing', 'triaging', 'verifying', 'delivering'].includes(t.status)
	);
	const queuedTasks = tasks.filter((t) => t.status === 'queued');
	const recentTasks = tasks
		.filter((t) => t.status === 'completed')
		.slice(0, 10)
		.map(adaptTaskToAgentRun);
	const devServers = repos.filter((r) => r.dev_url);

	return { threads, activeTasks, queuedTasks, recentTasks, repos, devServers, weather, workspaces, speedtest };
};
```

- [ ] **Step 3: Update `ui/src/routes/today/+page.svelte` to pass new props**

```svelte
<TodayView
	threads={data.threads}
	activeTasks={data.activeTasks}
	queuedTasks={data.queuedTasks}
	recentTasks={data.recentTasks}
	repos={data.repos}
	devServers={data.devServers}
	weather={data.weather}
	workspaces={data.workspaces}
	speedtest={data.speedtest}
/>
```

- [ ] **Step 4: Update `today-view.svelte` props + add dev-servers/workspaces/speedtest sections**

In the `<script>` props block, add the new imports and props:

```svelte
	import type { Repo, WeatherCurrent, Workspace, Speedtest } from '$lib/api/typed';
	// ...
	interface Props {
		threads?: Thread[];
		activeTasks?: Task[];
		queuedTasks?: Task[];
		recentTasks?: AgentRun[];
		repos?: Repo[];
		devServers?: Repo[];
		weather?: WeatherCurrent | null;
		workspaces?: Workspace[];
		speedtest?: Speedtest;
	}

	let {
		threads = [], activeTasks = [], queuedTasks = [], recentTasks = [],
		repos = [], devServers = [], weather = null, workspaces = [], speedtest = null
	}: Props = $props();
```

Add a "Dev servers" block and an "Active workspaces" block in the dashboard layout (place near the existing repos/threads sections). Use the same `Card`/`Heading`/`Meta` primitives already imported:

```svelte
{#if devServers.length > 0}
	<section class="flex flex-col gap-2">
		<Eyebrow>DEV SERVERS</Eyebrow>
		<div class="flex flex-wrap gap-2">
			{#each devServers as r (r.name)}
				<a href={r.dev_url} target="_blank" rel="noreferrer">
					<Chip tone="moss">{r.name} :{r.dev_port} ↗</Chip>
				</a>
			{/each}
		</div>
	</section>
{/if}

{#if workspaces.length > 0}
	<section class="flex flex-col gap-2">
		<Eyebrow>ACTIVE WORKSPACES</Eyebrow>
		{#each workspaces as ws (ws.session)}
			<a href={`/tasks/${ws.task_id}`} class="flex items-center gap-2 hover:underline">
				<StatusDot tone={ws.exited ? 'stone' : 'moss'} />
				<Meta size="xs">{ws.title ?? ws.session}{ws.repo ? ` · ${ws.repo}` : ''}</Meta>
			</a>
		{/each}
	</section>
{/if}

{#if speedtest}
	<Meta size="xs">↓ {speedtest.download_mbps} Mbps · ↑ {speedtest.upload_mbps} Mbps · {speedtest.ping_ms} ms</Meta>
{/if}
```

(Keep the existing weather card and threads/tasks sections. Only add; reuse the components already imported at the top of the file. If `Chip`/`StatusDot`/`Eyebrow` aren't already imported in this file, add them to the existing imports.)

- [ ] **Step 5: Verify typecheck + build, then test in browser**

Run: `cd ui && pnpm check && pnpm build`
Expected: clean. With backend running, confirm Today loads with no calls to removed routes (check the Network tab — no `/api/fields`, `/api/todos`, `/api/notebook/counts`), and shows dev servers + active workspaces + latest speedtest when data exists, and degrades gracefully (sections hidden) when empty.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Rewire Today dashboard with dev servers, workspaces, speedtest"
```

### Task 4.3: Frontend tests + stories for new views

**Files:**
- Create: `ui/src/lib/repos/repos-view.stories.ts`, `ui/src/lib/workspaces/workspaces-view.stories.ts`, `ui/src/lib/notebook/notebook-view.stories.ts`
- Modify/verify: existing adapters test still passes after widget removals

- [ ] **Step 1: Add a Storybook story per new view (follow the existing `*.stories.ts` pattern)**

Open an existing story (e.g. `ui/src/lib/library/library.stories.ts`) to copy its structure, then create one story each for ReposView, WorkspacesView, NotebookView with representative mock props (a couple of repos with/without `dev_url`; a running + an exited workspace; a small entries list).

- [ ] **Step 2: Run the frontend unit/story tests**

Run: `cd ui && pnpm test`
Expected: PASS (needs chromium per CLAUDE.md — if chromium is unavailable in this environment, run `pnpm check` instead and note the limitation).

- [ ] **Step 3: Add Playwright smoke routes**

Open `ui/tests/` (or wherever `pnpm test:e2e` points) and add the three new routes (`/repos`, `/workspaces`, `/notebook`) to the smoke list that asserts the page renders with mock-data fallback when the API is unreachable.

- [ ] **Step 4: Run e2e smoke**

Run: `cd ui && pnpm test:e2e`
Expected: PASS (mock fallback when API down).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "Add stories and smoke tests for Repos/Workspaces/Notebook views"
```

---

## Final verification

- [ ] Run full backend suite: `uv run pytest -q` — all pass.
- [ ] Run frontend checks: `cd ui && pnpm check && pnpm build` — clean.
- [ ] Manual smoke on the box (`uv run forge`): every spine destination loads; `/repos` dev links open; `/workspaces` reflects live sessions; `/notebook` browses read-only; Today makes no calls to removed routes.
- [ ] `grep -rn "fields\|todos\|purchases\|workouts\|places-map" ui/src forge | grep -v __pycache__ | grep -v node_modules` returns no live references (only spec/plan docs may mention them).
