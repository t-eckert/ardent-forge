# Self-Building Bootstrap — Phase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ardent Forge reads its own specs, produces plan PRs, and on plan-merge creates Linear tickets that the existing code handler then executes — completing the self-building loop.

**Architecture:** Two new handlers (`plan`, `tickets`) registered alongside the existing `code` handler. Two new watchers added to the coordinator tick: a spec-watcher that enqueues `plan` tasks from `ready-to-plan` specs, and a plan-merge-watcher that enqueues `tickets` tasks when plan PRs merge. Spec frontmatter is the single source of truth for lifecycle state. The `plan` handler uses Claude Opus for decomposition; the `tickets` handler is mechanical.

**Tech Stack:** Python 3.13, asyncio, pydantic, anthropic SDK, httpx (for Linear GraphQL), `python-frontmatter` for YAML-in-markdown, pytest/pytest-asyncio, existing `GitOps` + `LinearClient` + `CodeHandler` infrastructure.

---

## File Structure

**New files:**
- `forge/frontmatter.py` — parse/update spec frontmatter, status enum helpers
- `forge/handlers/plan.py` — the `plan` handler class
- `forge/handlers/tickets.py` — the `tickets` handler class
- `forge/watchers/__init__.py` — package init
- `forge/watchers/spec_watcher.py` — scan specs dir, enqueue plan tasks
- `forge/watchers/plan_merge_watcher.py` — scan merged plan PRs, enqueue tickets tasks
- `forge/linear/projects.py` — Linear Project/Issue creation helpers (separate from existing `client.py` to keep that file focused on polling)
- `tests/test_frontmatter.py`
- `tests/test_plan_handler.py`
- `tests/test_tickets_handler.py`
- `tests/test_spec_watcher.py`
- `tests/test_plan_merge_watcher.py`
- `tests/test_linear_projects.py`
- `tests/test_bootstrap_integration.py` — end-to-end smoke

**Modified files:**
- `forge/guardrails.py` — add handler-specific allowlists
- `forge/models.py` — add `PLAN` and `TICKETS` task types
- `forge/coordinator.py` — call watchers in tick
- `forge/main.py` — register plan/tickets handlers, construct watchers
- `forge/config.py` — add settings for AF repo clone target and Linear team id reuse
- `pyproject.toml` — add `python-frontmatter` dependency

---

## Task 1: Add python-frontmatter dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add dependency**

Edit `pyproject.toml` dependencies list to add `"python-frontmatter>=1.1"`:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "aiosqlite>=0.20",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "ulid-py>=1.1",
    "httpx>=0.28",
    "anthropic>=0.40",
    "python-frontmatter>=1.1",
]
```

- [ ] **Step 2: Sync**

Run: `uv sync`
Expected: `python-frontmatter` installed.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add python-frontmatter dep for spec frontmatter parsing"
```

---

## Task 2: Frontmatter module — SpecStatus enum and read/write helpers

**Files:**
- Create: `forge/frontmatter.py`
- Test: `tests/test_frontmatter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_frontmatter.py
from pathlib import Path

import pytest

from forge.frontmatter import (
    SpecStatus,
    read_spec,
    update_spec_status,
    find_specs_by_status,
)


def test_read_spec_returns_status_and_body(tmp_path: Path):
    spec = tmp_path / "foo.md"
    spec.write_text("---\nstatus: ready-to-plan\ntitle: Foo\n---\n\n# Foo\nBody text\n")
    parsed = read_spec(spec)
    assert parsed.status == SpecStatus.READY_TO_PLAN
    assert parsed.title == "Foo"
    assert "Body text" in parsed.body
    assert parsed.path == spec


def test_read_spec_missing_status_returns_none(tmp_path: Path):
    spec = tmp_path / "foo.md"
    spec.write_text("---\ntitle: Foo\n---\n\nBody\n")
    parsed = read_spec(spec)
    assert parsed.status is None


def test_update_spec_status_preserves_other_fields(tmp_path: Path):
    spec = tmp_path / "foo.md"
    spec.write_text("---\nstatus: ready-to-plan\ntitle: Foo\n---\n\nBody\n")
    update_spec_status(spec, SpecStatus.PLANNED)
    again = read_spec(spec)
    assert again.status == SpecStatus.PLANNED
    assert again.title == "Foo"
    assert "Body" in again.body


def test_find_specs_by_status(tmp_path: Path):
    (tmp_path / "a.md").write_text("---\nstatus: ready-to-plan\n---\nA\n")
    (tmp_path / "b.md").write_text("---\nstatus: draft\n---\nB\n")
    (tmp_path / "c.md").write_text("---\nstatus: ready-to-plan\n---\nC\n")
    (tmp_path / "not-a-spec.txt").write_text("ignored")

    found = find_specs_by_status(tmp_path, SpecStatus.READY_TO_PLAN)
    names = sorted(p.name for p in found)
    assert names == ["a.md", "c.md"]
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `uv run pytest tests/test_frontmatter.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'forge.frontmatter'"

- [ ] **Step 3: Implement `forge/frontmatter.py`**

```python
# forge/frontmatter.py
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import frontmatter


class SpecStatus(StrEnum):
    DRAFT = "draft"
    READY_TO_PLAN = "ready-to-plan"
    PLANNED = "planned"
    EXECUTING = "executing"
    DONE = "done"


@dataclass
class ParsedSpec:
    path: Path
    status: SpecStatus | None
    title: str | None
    body: str
    raw: dict


def read_spec(path: Path) -> ParsedSpec:
    post = frontmatter.load(str(path))
    raw_status = post.metadata.get("status")
    try:
        status = SpecStatus(raw_status) if raw_status else None
    except ValueError:
        status = None
    return ParsedSpec(
        path=path,
        status=status,
        title=post.metadata.get("title"),
        body=post.content,
        raw=dict(post.metadata),
    )


def update_spec_status(path: Path, status: SpecStatus) -> None:
    post = frontmatter.load(str(path))
    post["status"] = status.value
    with open(path, "wb") as f:
        frontmatter.dump(post, f)


def find_specs_by_status(root: Path, status: SpecStatus) -> list[Path]:
    results: list[Path] = []
    for md in sorted(root.glob("*.md")):
        try:
            parsed = read_spec(md)
        except Exception:
            continue
        if parsed.status == status:
            results.append(md)
    return results
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `uv run pytest tests/test_frontmatter.py -v`
Expected: All four tests PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/frontmatter.py tests/test_frontmatter.py
git commit -m "feat(frontmatter): spec status enum and read/update helpers"
```

---

## Task 3: Extend guardrails with handler-specific write allowlists

**Files:**
- Modify: `forge/guardrails.py`
- Test: extend `tests/test_guardrails.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_guardrails.py`:

```python
from forge.guardrails import check_handler_allowlist


def test_plan_handler_allows_plans_and_specs():
    violations = check_handler_allowlist(
        handler="plan",
        repo="t-eckert/ardent-forge",
        changed_files=[
            "docs/superpowers/plans/2026-04-15-foo.md",
            "docs/superpowers/specs/2026-04-15-foo.md",
        ],
    )
    assert violations is None


def test_plan_handler_rejects_code_files():
    violations = check_handler_allowlist(
        handler="plan",
        repo="t-eckert/ardent-forge",
        changed_files=["forge/main.py"],
    )
    assert violations is not None
    assert "forge/main.py" in violations


def test_tickets_handler_allows_specs_only():
    ok = check_handler_allowlist(
        handler="tickets",
        repo="t-eckert/ardent-forge",
        changed_files=["docs/superpowers/specs/2026-04-15-foo.md"],
    )
    assert ok is None
    bad = check_handler_allowlist(
        handler="tickets",
        repo="t-eckert/ardent-forge",
        changed_files=["docs/superpowers/plans/x.md"],
    )
    assert bad is not None


def test_handler_allowlist_bypassed_for_other_repos():
    # The allowlist only applies to the AF self-repo; other repos unrestricted
    ok = check_handler_allowlist(
        handler="plan",
        repo="t-eckert/some-other-repo",
        changed_files=["anywhere.py"],
    )
    assert ok is None
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `uv run pytest tests/test_guardrails.py -v`
Expected: FAIL with "ImportError: cannot import name 'check_handler_allowlist'"

- [ ] **Step 3: Update `forge/guardrails.py`**

```python
"""Safety guardrails for self-modification."""

SELF_REPO = "t-eckert/ardent-forge"

PROTECTED_PATHS = [
    "nix/",
    "CLAUDE.md",
    "forge/guardrails.py",
]

HANDLER_ALLOWLISTS: dict[str, list[str]] = {
    "plan": [
        "docs/superpowers/plans/",
        "docs/superpowers/specs/",
    ],
    "tickets": [
        "docs/superpowers/specs/",
    ],
}


def check_self_modification(repo: str, changed_files: list[str]) -> str | None:
    if repo != SELF_REPO:
        return None
    violations = []
    for file_path in changed_files:
        for protected in PROTECTED_PATHS:
            if file_path == protected or file_path.startswith(protected):
                violations.append(file_path)
                break
    if violations:
        files = ", ".join(violations)
        return f"Self-modification guardrail: cannot modify protected files: {files}"
    return None


def check_handler_allowlist(
    handler: str, repo: str, changed_files: list[str]
) -> str | None:
    """For handlers with a narrow write scope, reject files outside the allowlist.

    Only enforced for the AF self-repo; other repos are unrestricted.
    """
    if repo != SELF_REPO:
        return None
    allowlist = HANDLER_ALLOWLISTS.get(handler)
    if allowlist is None:
        return None
    violations = []
    for file_path in changed_files:
        if not any(file_path.startswith(prefix) for prefix in allowlist):
            violations.append(file_path)
    if violations:
        files = ", ".join(violations)
        return f"Handler '{handler}' allowlist violation: {files}"
    return None
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `uv run pytest tests/test_guardrails.py -v`
Expected: all tests PASS (existing ones remain green).

- [ ] **Step 5: Commit**

```bash
git add forge/guardrails.py tests/test_guardrails.py
git commit -m "feat(guardrails): handler-specific write allowlists for plan/tickets"
```

---

## Task 4: Add PLAN and TICKETS task types

**Files:**
- Modify: `forge/models.py`
- Test: extend `tests/test_models.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_models.py`:

```python
def test_task_type_includes_plan_and_tickets():
    from forge.models import TaskType
    assert TaskType.PLAN == "plan"
    assert TaskType.TICKETS == "tickets"
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_models.py -v -k plan_and_tickets`
Expected: FAIL with AttributeError on TaskType.PLAN.

- [ ] **Step 3: Add enum values**

In `forge/models.py`, extend `TaskType`:

```python
class TaskType(StrEnum):
    CODE = "code"
    RESEARCH = "research"
    REPORT = "report"
    NOTEBOOK = "notebook"
    TRIAGE = "triage"
    PLAN = "plan"
    TICKETS = "tickets"
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: all model tests PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/models.py tests/test_models.py
git commit -m "feat(models): add plan and tickets task types"
```

---

## Task 5: Plan handler — skeleton with triage and prompt building

**Files:**
- Create: `forge/handlers/plan.py`
- Test: `tests/test_plan_handler.py`

The plan handler follows the same protocol as `CodeHandler`: `triage`, `execute`, `verify`, `deliver`. Execute is split across Tasks 5–8 for TDD granularity; this task establishes the skeleton and prompt builder.

- [ ] **Step 1: Write failing tests for triage and prompt building**

```python
# tests/test_plan_handler.py
from pathlib import Path

import pytest

from forge.handlers.plan import PlanHandler, build_plan_prompt
from forge.models import Task, TaskSource, TaskType


def _task(description: str = "spec: docs/superpowers/specs/2026-04-15-foo.md") -> Task:
    return Task.new(
        task_type=TaskType.PLAN,
        source=TaskSource.WEBHOOK,
        title="plan spec",
        description=description,
        repo="t-eckert/ardent-forge",
    )


async def test_triage_accepts_task_with_spec_path_in_description():
    handler = PlanHandler(workspace_dir="/tmp/wsp", specs_dir="docs/superpowers/specs")
    assert await handler.triage(_task()) is True


async def test_triage_rejects_task_without_spec_path():
    handler = PlanHandler(workspace_dir="/tmp/wsp", specs_dir="docs/superpowers/specs")
    task = _task(description="no spec here")
    assert await handler.triage(task) is False


def test_build_plan_prompt_mentions_spec_and_format():
    spec_text = "# My Spec\n\nBuild a widget."
    prompt = build_plan_prompt(spec_path="docs/superpowers/specs/foo.md", spec_body=spec_text)
    assert "# My Spec" in prompt
    assert "docs/superpowers/plans/" in prompt
    assert "numbered" in prompt.lower()
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_plan_handler.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement skeleton**

```python
# forge/handlers/plan.py
import logging
import re
from pathlib import Path

from forge.claude import ClaudeRunner
from forge.git import GitOps
from forge.guardrails import check_handler_allowlist
from forge.models import Task

logger = logging.getLogger(__name__)

SPEC_PATH_RE = re.compile(r"(docs/superpowers/specs/[\w\-.]+\.md)")


def extract_spec_path(description: str) -> str | None:
    match = SPEC_PATH_RE.search(description or "")
    return match.group(1) if match else None


def build_plan_prompt(spec_path: str, spec_body: str) -> str:
    return f"""You are the Ardent Forge planner. Read the spec below and produce an implementation plan.

Write the plan to `docs/superpowers/plans/` using the same filename date-prefix as the spec.
Format: numbered top-level tasks, each with bite-sized steps, exact file paths, complete code blocks, explicit test-first TDD cadence, and a commit step. Match the style of existing plans in docs/superpowers/plans/.

After writing the plan file, also update the spec file's frontmatter `status` field from `ready-to-plan` to `planned`.

Do NOT modify any other files. Your write scope is limited to the plan file and the spec's frontmatter.

Spec path: {spec_path}

Spec content:
---
{spec_body}
---
"""


class PlanHandler:
    task_type: str = "plan"

    def __init__(
        self,
        workspace_dir: str = "/var/lib/ardent-forge/repos",
        specs_dir: str = "docs/superpowers/specs",
        self_repo: str = "t-eckert/ardent-forge",
        claude_model: str = "claude-opus-4-20250514",
        claude_timeout: int = 600,
    ):
        self._git = GitOps(workspace_dir)
        self._claude = ClaudeRunner(model=claude_model, timeout=claude_timeout)
        self._specs_dir = specs_dir
        self._self_repo = self_repo

    async def triage(self, task: Task) -> bool:
        spec_path = extract_spec_path(task.description)
        if not spec_path:
            logger.warning(f"Task {task.id} has no spec path in description")
            return False
        return True

    async def execute(self, task: Task) -> dict:
        raise NotImplementedError  # Task 6

    async def verify(self, task: Task) -> bool:
        raise NotImplementedError  # Task 7

    async def deliver(self, task: Task) -> dict:
        raise NotImplementedError  # Task 8
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `uv run pytest tests/test_plan_handler.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/handlers/plan.py tests/test_plan_handler.py
git commit -m "feat(plan): handler skeleton with triage and prompt builder"
```

---

## Task 6: Plan handler — execute (clone, worktree, Claude, write)

**Files:**
- Modify: `forge/handlers/plan.py`
- Test: extend `tests/test_plan_handler.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_plan_handler.py`:

```python
from unittest.mock import AsyncMock, MagicMock


async def test_execute_clones_creates_worktree_and_invokes_claude(tmp_path):
    handler = PlanHandler(workspace_dir=str(tmp_path / "ws"))

    repo_path = tmp_path / "ardent-forge"
    repo_path.mkdir()
    specs = repo_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    spec_file = specs / "2026-04-15-foo.md"
    spec_file.write_text("---\nstatus: ready-to-plan\ntitle: Foo\n---\n\n# Foo\nDetails.\n")

    worktree_path = tmp_path / "wt"
    worktree_path.mkdir()
    (worktree_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (worktree_path / "docs" / "superpowers" / "specs" / "2026-04-15-foo.md").write_text(
        spec_file.read_text()
    )

    handler._git.ensure_repo = AsyncMock(return_value=str(repo_path))
    handler._git.create_worktree = AsyncMock(return_value=str(worktree_path))
    handler._claude.run = AsyncMock(return_value="claude output")

    task = _task(description="spec: docs/superpowers/specs/2026-04-15-foo.md")
    result = await handler.execute(task)

    assert result["worktree_path"] == str(worktree_path)
    assert result["spec_path"] == "docs/superpowers/specs/2026-04-15-foo.md"
    assert result["branch_name"].startswith("forge/plan-")
    handler._claude.run.assert_awaited_once()
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_plan_handler.py::test_execute_clones_creates_worktree_and_invokes_claude -v`
Expected: FAIL with NotImplementedError.

- [ ] **Step 3: Implement `execute`**

Replace the `execute` stub in `forge/handlers/plan.py`:

```python
    async def execute(self, task: Task) -> dict:
        spec_path = extract_spec_path(task.description)
        if not spec_path:
            raise RuntimeError(f"No spec path in task {task.id}")

        repo_url = f"https://github.com/{self._self_repo}.git"
        branch_name = f"forge/plan-{task.id[:12]}"

        repo_path = await self._git.ensure_repo(repo_url, self._self_repo)
        worktree_path = await self._git.create_worktree(repo_path, branch_name)

        spec_abs = Path(worktree_path) / spec_path
        if not spec_abs.exists():
            raise RuntimeError(f"Spec file not found in worktree: {spec_abs}")
        spec_body = spec_abs.read_text()

        prompt = build_plan_prompt(spec_path=spec_path, spec_body=spec_body)
        output = await self._claude.run(prompt, worktree_path)

        return {
            "worktree_path": worktree_path,
            "repo_path": repo_path,
            "branch_name": branch_name,
            "spec_path": spec_path,
            "claude_output": output[:2000],
        }
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_plan_handler.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/handlers/plan.py tests/test_plan_handler.py
git commit -m "feat(plan): execute clones, creates worktree, runs Claude"
```

---

## Task 7: Plan handler — verify (guardrails on diff)

**Files:**
- Modify: `forge/handlers/plan.py`
- Test: extend `tests/test_plan_handler.py`

Verify parses the worktree's git diff, collects changed files, and ensures every one sits inside the `plan` handler's allowlist.

- [ ] **Step 1: Write failing test**

Append to `tests/test_plan_handler.py`:

```python
async def test_verify_passes_when_diff_is_plan_and_spec_only():
    handler = PlanHandler(workspace_dir="/tmp/wsp")
    handler._git.get_changed_files = AsyncMock(return_value=[
        "docs/superpowers/plans/2026-04-15-foo.md",
        "docs/superpowers/specs/2026-04-15-foo.md",
    ])
    task = _task()
    task.handler_data = {"worktree_path": "/tmp/wt"}
    assert await handler.verify(task) is True


async def test_verify_fails_when_diff_touches_code():
    handler = PlanHandler(workspace_dir="/tmp/wsp")
    handler._git.get_changed_files = AsyncMock(return_value=[
        "docs/superpowers/plans/2026-04-15-foo.md",
        "forge/main.py",
    ])
    task = _task()
    task.handler_data = {"worktree_path": "/tmp/wt"}
    assert await handler.verify(task) is False


async def test_verify_fails_when_no_worktree():
    handler = PlanHandler(workspace_dir="/tmp/wsp")
    task = _task()
    task.handler_data = {}
    assert await handler.verify(task) is False
```

- [ ] **Step 2: Add `get_changed_files` to GitOps**

Modify `forge/git.py`, add method:

```python
    async def get_changed_files(self, worktree_path: str, base_branch: str = "main") -> list[str]:
        output = await self._run(
            f"git diff --name-only {base_branch}...HEAD",
            cwd=worktree_path,
        )
        return [line.strip() for line in output.splitlines() if line.strip()]
```

Add a test for it in `tests/test_git.py` (scan existing patterns there to match style).

- [ ] **Step 3: Run plan handler tests to confirm failure**

Run: `uv run pytest tests/test_plan_handler.py -v`
Expected: the 3 new verify tests FAIL with NotImplementedError.

- [ ] **Step 4: Implement `verify`**

Replace the verify stub in `forge/handlers/plan.py`:

```python
    async def verify(self, task: Task) -> bool:
        worktree_path = task.handler_data.get("worktree_path")
        if not worktree_path:
            logger.error(f"No worktree_path in handler_data for task {task.id}")
            return False
        try:
            changed = await self._git.get_changed_files(worktree_path, base_branch="main")
        except RuntimeError as e:
            logger.error(f"Failed to list changed files: {e}")
            return False
        violation = check_handler_allowlist(
            handler=self.task_type,
            repo=self._self_repo,
            changed_files=changed,
        )
        if violation:
            logger.error(f"Verification failed for task {task.id}: {violation}")
            return False
        if not changed:
            logger.error(f"Plan handler produced no changes for task {task.id}")
            return False
        return True
```

- [ ] **Step 5: Run to confirm pass**

Run: `uv run pytest tests/test_plan_handler.py tests/test_git.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add forge/handlers/plan.py forge/git.py tests/test_plan_handler.py tests/test_git.py
git commit -m "feat(plan): verify diff against handler allowlist"
```

---

## Task 8: Plan handler — deliver (commit, push, PR, bump spec frontmatter)

**Files:**
- Modify: `forge/handlers/plan.py`
- Modify: `forge/git.py` (add `commit_all` if absent)
- Test: extend `tests/test_plan_handler.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_plan_handler.py`:

```python
async def test_deliver_commits_opens_pr_and_returns_url():
    handler = PlanHandler(workspace_dir="/tmp/wsp")
    handler._git.commit_all = AsyncMock(return_value=None)
    handler._git.create_pr = AsyncMock(return_value="https://github.com/x/y/pull/1")
    handler._git.cleanup_worktree = AsyncMock(return_value=None)

    task = _task()
    task.handler_data = {
        "worktree_path": "/tmp/wt",
        "repo_path": "/tmp/repo",
        "branch_name": "forge/plan-abc",
        "spec_path": "docs/superpowers/specs/2026-04-15-foo.md",
    }
    result = await handler.deliver(task)

    assert result["status"] == "delivered"
    assert result["pr_url"] == "https://github.com/x/y/pull/1"
    handler._git.commit_all.assert_awaited_once()
    handler._git.create_pr.assert_awaited_once()
```

- [ ] **Step 2: Add `commit_all` to GitOps**

Modify `forge/git.py`:

```python
    async def commit_all(self, worktree_path: str, message: str) -> None:
        await self._run("git add -A", cwd=worktree_path)
        # Succeeds when nothing staged: use --allow-empty? No — fail if nothing.
        status = await self._run("git status --porcelain", cwd=worktree_path)
        if not status.strip():
            raise RuntimeError("commit_all called but nothing staged")
        safe_msg = message.replace('"', '\\"')
        await self._run(f'git commit -m "{safe_msg}"', cwd=worktree_path)
```

- [ ] **Step 3: Implement `deliver`**

Replace the deliver stub in `forge/handlers/plan.py`:

```python
    async def deliver(self, task: Task) -> dict:
        worktree_path = task.handler_data.get("worktree_path")
        repo_path = task.handler_data.get("repo_path")
        branch_name = task.handler_data.get("branch_name", "")
        spec_path = task.handler_data.get("spec_path")

        if not worktree_path or not repo_path or not spec_path:
            return {"status": "delivered", "error": "Missing handler_data"}

        commit_msg = f"plan: {task.title}"
        await self._git.commit_all(worktree_path, commit_msg)

        body = (
            f"Plan generated from {spec_path}.\n\n"
            "On merge, Ardent Forge will create Linear tickets for each numbered step.\n\n"
            "---\nAutomated by Ardent Forge (plan handler)"
        )
        try:
            pr_url = await self._git.create_pr(
                worktree_path=worktree_path,
                title=f"plan: {task.title}",
                body=body,
            )
        except RuntimeError as e:
            logger.error(f"PR creation failed: {e}")
            pr_url = f"PR creation failed: {e}"

        try:
            await self._git.cleanup_worktree(repo_path, worktree_path)
        except RuntimeError:
            logger.warning(f"Failed to cleanup worktree {worktree_path}")

        return {
            "status": "delivered",
            "pr_url": pr_url,
            "branch": branch_name,
            "spec_path": spec_path,
        }
```

Note: the spec frontmatter bump is done by Claude during `execute` (per the prompt). Verify already ensures the spec change is in the diff.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_plan_handler.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/handlers/plan.py forge/git.py tests/test_plan_handler.py
git commit -m "feat(plan): deliver commits and opens plan PR"
```

---

## Task 9: Spec watcher — scan ready-to-plan specs in the AF repo clone

**Files:**
- Create: `forge/watchers/__init__.py` (empty)
- Create: `forge/watchers/spec_watcher.py`
- Test: `tests/test_spec_watcher.py`

The spec watcher works against a local clone of the AF repo (the same `workspace_dir` the handlers use). Each tick it `git fetch`es, reads the specs directory on `origin/main`, finds `ready-to-plan` specs, and enqueues a `plan` task per spec it hasn't already enqueued. Dedupe by `source_id = f"spec:{spec_path}"`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_spec_watcher.py
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from forge.frontmatter import SpecStatus
from forge.models import TaskSource, TaskType
from forge.watchers.spec_watcher import SpecWatcher


class FakeStore:
    def __init__(self):
        self.saved = []
        self.existing_ids: set[str] = set()

    async def find_by_source_id(self, sid):
        return "exists" if sid in self.existing_ids else None

    async def save(self, task):
        self.saved.append(task)


async def test_spec_watcher_enqueues_ready_specs(tmp_path: Path):
    specs_dir = tmp_path / "repo" / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "2026-04-15-a.md").write_text(
        "---\nstatus: ready-to-plan\ntitle: A\n---\n\nBody\n"
    )
    (specs_dir / "2026-04-15-b.md").write_text(
        "---\nstatus: draft\n---\n\nBody\n"
    )

    store = FakeStore()
    fetch = AsyncMock()
    watcher = SpecWatcher(
        store=store,
        repo_path=str(tmp_path / "repo"),
        specs_subdir="docs/superpowers/specs",
        fetch_fn=fetch,
    )
    created = await watcher.poll()

    assert created == 1
    assert len(store.saved) == 1
    task = store.saved[0]
    assert task.type == TaskType.PLAN
    assert task.source == TaskSource.WEBHOOK
    assert task.source_id == "spec:docs/superpowers/specs/2026-04-15-a.md"
    assert "docs/superpowers/specs/2026-04-15-a.md" in task.description
    fetch.assert_awaited_once()


async def test_spec_watcher_deduplicates(tmp_path: Path):
    specs_dir = tmp_path / "repo" / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "2026-04-15-a.md").write_text(
        "---\nstatus: ready-to-plan\n---\n\nBody\n"
    )
    store = FakeStore()
    store.existing_ids.add("spec:docs/superpowers/specs/2026-04-15-a.md")

    watcher = SpecWatcher(
        store=store,
        repo_path=str(tmp_path / "repo"),
        specs_subdir="docs/superpowers/specs",
        fetch_fn=AsyncMock(),
    )
    created = await watcher.poll()
    assert created == 0
    assert store.saved == []
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_spec_watcher.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement `forge/watchers/spec_watcher.py`**

```python
# forge/watchers/spec_watcher.py
import logging
from pathlib import Path
from typing import Awaitable, Callable

from forge.frontmatter import SpecStatus, find_specs_by_status
from forge.models import Task, TaskSource, TaskType

logger = logging.getLogger(__name__)


class SpecWatcher:
    def __init__(
        self,
        store,
        repo_path: str,
        specs_subdir: str = "docs/superpowers/specs",
        fetch_fn: Callable[[], Awaitable[None]] | None = None,
        self_repo: str = "t-eckert/ardent-forge",
    ):
        self._store = store
        self._repo_path = Path(repo_path)
        self._specs_subdir = specs_subdir
        self._fetch = fetch_fn
        self._self_repo = self_repo

    async def poll(self) -> int:
        if self._fetch:
            try:
                await self._fetch()
            except Exception:
                logger.exception("spec watcher fetch failed; proceeding with local state")

        specs_dir = self._repo_path / self._specs_subdir
        if not specs_dir.is_dir():
            return 0

        ready = find_specs_by_status(specs_dir, SpecStatus.READY_TO_PLAN)
        created = 0
        for spec_abs in ready:
            rel = str(spec_abs.relative_to(self._repo_path))
            source_id = f"spec:{rel}"
            if await self._store.find_by_source_id(source_id) is not None:
                continue
            task = Task.new(
                task_type=TaskType.PLAN,
                source=TaskSource.WEBHOOK,
                title=f"plan {spec_abs.stem}",
                description=f"spec: {rel}",
                source_id=source_id,
                repo=self._self_repo,
            )
            await self._store.save(task)
            logger.info(f"Enqueued plan task for {rel}")
            created += 1
        return created
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_spec_watcher.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/watchers/__init__.py forge/watchers/spec_watcher.py tests/test_spec_watcher.py
git commit -m "feat(watchers): spec watcher enqueues plan tasks for ready specs"
```

---

## Task 10: Linear Projects and Issues creation API

**Files:**
- Create: `forge/linear/projects.py`
- Test: `tests/test_linear_projects.py`

- [ ] **Step 1: Write failing tests using respx**

```python
# tests/test_linear_projects.py
import httpx
import pytest
import respx

from forge.linear.client import LinearClient
from forge.linear.projects import LinearProjectsAPI


@respx.mock
async def test_create_project_returns_id():
    respx.post("https://api.linear.app/graphql").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"projectCreate": {"success": True, "project": {"id": "p1", "url": "https://linear.app/x/project/p1"}}}},
        )
    )
    client = LinearClient(api_key="k")
    api = LinearProjectsAPI(client)
    project_id, url = await api.create_project(
        team_id="team-1", name="Phase 0", description="desc"
    )
    assert project_id == "p1"
    assert url.endswith("/p1")


@respx.mock
async def test_create_issue_returns_id_and_identifier():
    respx.post("https://api.linear.app/graphql").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"issueCreate": {"success": True, "issue": {"id": "i1", "identifier": "FORGE-42", "url": "u"}}}},
        )
    )
    client = LinearClient(api_key="k")
    api = LinearProjectsAPI(client)
    issue_id, identifier, url = await api.create_issue(
        team_id="team-1",
        project_id="p1",
        title="Step 1",
        description="body",
        labels=["devagent"],
        priority=2,
    )
    assert issue_id == "i1"
    assert identifier == "FORGE-42"


@respx.mock
async def test_get_label_id_by_name():
    respx.post("https://api.linear.app/graphql").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"issueLabels": {"nodes": [{"id": "lab1", "name": "devagent"}]}}},
        )
    )
    client = LinearClient(api_key="k")
    api = LinearProjectsAPI(client)
    lid = await api.get_label_id(team_id="team-1", name="devagent")
    assert lid == "lab1"
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_linear_projects.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement `forge/linear/projects.py`**

```python
# forge/linear/projects.py
import logging

from forge.linear.client import LinearClient

logger = logging.getLogger(__name__)


class LinearProjectsAPI:
    def __init__(self, client: LinearClient):
        self._client = client

    async def create_project(
        self, team_id: str, name: str, description: str
    ) -> tuple[str, str]:
        query = """
        mutation ProjectCreate($teamIds: [String!]!, $name: String!, $description: String!) {
            projectCreate(input: { teamIds: $teamIds, name: $name, description: $description }) {
                success
                project { id url }
            }
        }
        """
        result = await self._client._query(
            query, {"teamIds": [team_id], "name": name, "description": description}
        )
        project = result["data"]["projectCreate"]["project"]
        return project["id"], project.get("url", "")

    async def get_label_id(self, team_id: str, name: str) -> str | None:
        query = """
        query Labels($teamId: ID!) {
            issueLabels(filter: { team: { id: { eq: $teamId } } }) {
                nodes { id name }
            }
        }
        """
        result = await self._client._query(query, {"teamId": team_id})
        for node in result["data"]["issueLabels"]["nodes"]:
            if node["name"].lower() == name.lower():
                return node["id"]
        return None

    async def create_issue(
        self,
        team_id: str,
        project_id: str,
        title: str,
        description: str,
        labels: list[str] | None = None,
        priority: int | None = None,
        label_ids: list[str] | None = None,
    ) -> tuple[str, str, str]:
        query = """
        mutation IssueCreate($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue { id identifier url }
            }
        }
        """
        input_payload: dict = {
            "teamId": team_id,
            "projectId": project_id,
            "title": title,
            "description": description,
        }
        if priority is not None:
            input_payload["priority"] = priority
        resolved_label_ids: list[str] = list(label_ids or [])
        if labels and not resolved_label_ids:
            for label_name in labels:
                lid = await self.get_label_id(team_id, label_name)
                if lid:
                    resolved_label_ids.append(lid)
        if resolved_label_ids:
            input_payload["labelIds"] = resolved_label_ids

        result = await self._client._query(query, {"input": input_payload})
        issue = result["data"]["issueCreate"]["issue"]
        return issue["id"], issue["identifier"], issue.get("url", "")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_linear_projects.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/linear/projects.py tests/test_linear_projects.py
git commit -m "feat(linear): project and issue creation API"
```

---

## Task 11: Plan-markdown parser

**Files:**
- Create: `forge/handlers/tickets.py` (parser portion only this task)
- Test: `tests/test_tickets_handler.py`

Parse `## Task N: <title>` headers and the content up to the next `## Task` or `---` as one step. Each Task becomes a Linear issue.

- [ ] **Step 1: Write failing test**

```python
# tests/test_tickets_handler.py
from forge.handlers.tickets import parse_plan_tasks

PLAN_SAMPLE = """# Foo Plan

**Goal:** build it

---

## Task 1: First thing

**Files:**
- Create: `a.py`

- [ ] Step 1: do a

## Task 2: Second thing

**Files:**
- Modify: `b.py`

- [ ] Step 1: do b

---

## Success Criteria
- something
"""


def test_parse_plan_tasks_returns_one_per_task_header():
    tasks = parse_plan_tasks(PLAN_SAMPLE)
    assert len(tasks) == 2
    assert tasks[0].number == 1
    assert tasks[0].title == "First thing"
    assert "do a" in tasks[0].body
    assert tasks[1].number == 2
    assert tasks[1].title == "Second thing"
    assert "do b" in tasks[1].body
    # body should not include the next task's content
    assert "do b" not in tasks[0].body


def test_parse_plan_tasks_empty_when_no_headers():
    assert parse_plan_tasks("# Nothing here\n\nJust text.") == []
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_tickets_handler.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement parser in `forge/handlers/tickets.py`**

```python
# forge/handlers/tickets.py
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

TASK_HEADER_RE = re.compile(r"^## Task (\d+): (.+?)$", re.MULTILINE)


@dataclass
class PlanTask:
    number: int
    title: str
    body: str


def parse_plan_tasks(plan_markdown: str) -> list[PlanTask]:
    matches = list(TASK_HEADER_RE.finditer(plan_markdown))
    results: list[PlanTask] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(plan_markdown)
        body = plan_markdown[start:end].strip()
        # Trim a trailing horizontal-rule + non-task section if present
        body = re.split(r"\n---\n", body, maxsplit=1)[0].strip()
        results.append(
            PlanTask(number=int(m.group(1)), title=m.group(2).strip(), body=body)
        )
    return results
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_tickets_handler.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/handlers/tickets.py tests/test_tickets_handler.py
git commit -m "feat(tickets): parse plan markdown into PlanTask list"
```

---

## Task 12: Tickets handler — full handler (triage, execute, verify, deliver)

**Files:**
- Modify: `forge/handlers/tickets.py`
- Test: extend `tests/test_tickets_handler.py`

The tickets handler:
- triage: accepts tasks whose description contains `plan: <plan-path>`
- execute: clones repo, reads plan file from main, calls LinearProjectsAPI to create Project + Issues, bumps spec frontmatter to `executing`, commits directly to main (no PR)
- verify: confirms Linear IDs returned and frontmatter updated
- deliver: pushes the frontmatter commit to main; returns summary

- [ ] **Step 1: Write failing tests**

Append to `tests/test_tickets_handler.py`:

```python
from pathlib import Path
from unittest.mock import AsyncMock

from forge.handlers.tickets import TicketsHandler, extract_plan_path
from forge.models import Task, TaskSource, TaskType


def _ticket_task(desc: str) -> Task:
    return Task.new(
        task_type=TaskType.TICKETS,
        source=TaskSource.WEBHOOK,
        title="tickets",
        description=desc,
        repo="t-eckert/ardent-forge",
    )


def test_extract_plan_path():
    assert extract_plan_path("plan: docs/superpowers/plans/2026-04-15-foo.md") == "docs/superpowers/plans/2026-04-15-foo.md"
    assert extract_plan_path("nothing") is None


async def test_tickets_triage_requires_plan_path():
    handler = TicketsHandler(
        workspace_dir="/tmp/w", linear=AsyncMock(), team_id="t1"
    )
    assert await handler.triage(_ticket_task("plan: docs/superpowers/plans/x.md")) is True
    assert await handler.triage(_ticket_task("no")) is False


async def test_tickets_execute_creates_project_and_issues(tmp_path: Path):
    repo = tmp_path / "repo"
    plans = repo / "docs" / "superpowers" / "plans"
    specs = repo / "docs" / "superpowers" / "specs"
    plans.mkdir(parents=True)
    specs.mkdir(parents=True)
    (plans / "2026-04-15-foo.md").write_text(
        "# Foo Plan\n\n## Task 1: One\n\nbody1\n\n## Task 2: Two\n\nbody2\n"
    )
    (specs / "2026-04-15-foo.md").write_text(
        "---\nstatus: planned\ntitle: Foo\n---\n\nbody\n"
    )

    linear = AsyncMock()
    linear.create_project = AsyncMock(return_value=("p1", "https://linear.app/x/p1"))
    linear.get_label_id = AsyncMock(return_value="lab-devagent")
    linear.create_issue = AsyncMock(side_effect=[
        ("i1", "FORGE-1", "u1"),
        ("i2", "FORGE-2", "u2"),
    ])

    handler = TicketsHandler(
        workspace_dir="/tmp/w", linear=linear, team_id="t1",
        self_repo="t-eckert/ardent-forge",
    )
    handler._git.ensure_repo = AsyncMock(return_value=str(repo))

    task = _ticket_task(
        "plan: docs/superpowers/plans/2026-04-15-foo.md spec: docs/superpowers/specs/2026-04-15-foo.md"
    )
    result = await handler.execute(task)

    assert result["project_id"] == "p1"
    assert result["issue_identifiers"] == ["FORGE-1", "FORGE-2"]
    linear.create_project.assert_awaited_once()
    assert linear.create_issue.await_count == 2
    # Spec frontmatter should be updated
    from forge.frontmatter import read_spec, SpecStatus
    parsed = read_spec(specs / "2026-04-15-foo.md")
    assert parsed.status == SpecStatus.EXECUTING
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_tickets_handler.py -v`
Expected: FAIL (missing class/functions).

- [ ] **Step 3: Implement handler in `forge/handlers/tickets.py`** (append below the parser)

```python
# Append to forge/handlers/tickets.py
from pathlib import Path

from forge.frontmatter import SpecStatus, update_spec_status
from forge.git import GitOps
from forge.guardrails import check_handler_allowlist
from forge.linear.projects import LinearProjectsAPI
from forge.models import Task

PLAN_PATH_RE = re.compile(r"plan:\s*(docs/superpowers/plans/[\w\-.]+\.md)")
SPEC_PATH_RE = re.compile(r"spec:\s*(docs/superpowers/specs/[\w\-.]+\.md)")


def extract_plan_path(description: str) -> str | None:
    m = PLAN_PATH_RE.search(description or "")
    return m.group(1) if m else None


def extract_spec_path_from_tickets_task(description: str) -> str | None:
    m = SPEC_PATH_RE.search(description or "")
    return m.group(1) if m else None


class TicketsHandler:
    task_type: str = "tickets"

    def __init__(
        self,
        workspace_dir: str,
        linear: LinearProjectsAPI,
        team_id: str,
        self_repo: str = "t-eckert/ardent-forge",
        label: str = "devagent",
    ):
        self._git = GitOps(workspace_dir)
        self._linear = linear
        self._team_id = team_id
        self._self_repo = self_repo
        self._label = label

    async def triage(self, task: Task) -> bool:
        return extract_plan_path(task.description) is not None

    async def execute(self, task: Task) -> dict:
        plan_rel = extract_plan_path(task.description)
        spec_rel = extract_spec_path_from_tickets_task(task.description)
        if not plan_rel or not spec_rel:
            raise RuntimeError(f"Task {task.id} missing plan or spec path")

        repo_url = f"https://github.com/{self._self_repo}.git"
        repo_path = await self._git.ensure_repo(repo_url, self._self_repo)

        plan_abs = Path(repo_path) / plan_rel
        spec_abs = Path(repo_path) / spec_rel
        if not plan_abs.exists() or not spec_abs.exists():
            raise RuntimeError("plan or spec file missing in repo clone")

        plan_markdown = plan_abs.read_text()
        plan_tasks = parse_plan_tasks(plan_markdown)
        if not plan_tasks:
            raise RuntimeError(f"No tasks parsed from {plan_rel}")

        project_name = f"{task.title} ({spec_abs.stem})"
        project_desc = f"Generated from {plan_rel}\nSpec: {spec_rel}"
        project_id, project_url = await self._linear.create_project(
            team_id=self._team_id,
            name=project_name,
            description=project_desc,
        )

        label_id = await self._linear.get_label_id(self._team_id, self._label)
        label_ids = [label_id] if label_id else []

        identifiers: list[str] = []
        issue_urls: list[str] = []
        for pt in plan_tasks:
            priority = 2 if pt.number == 1 else 3  # high for first, normal for rest
            _, identifier, url = await self._linear.create_issue(
                team_id=self._team_id,
                project_id=project_id,
                title=f"{pt.title} (Task {pt.number})",
                description=pt.body + f"\n\n---\nPlan: {plan_rel}\nSpec: {spec_rel}",
                label_ids=label_ids,
                priority=priority,
            )
            identifiers.append(identifier)
            issue_urls.append(url)

        update_spec_status(spec_abs, SpecStatus.EXECUTING)

        return {
            "project_id": project_id,
            "project_url": project_url,
            "issue_identifiers": identifiers,
            "issue_urls": issue_urls,
            "repo_path": repo_path,
            "spec_path": spec_rel,
            "plan_path": plan_rel,
        }

    async def verify(self, task: Task) -> bool:
        data = task.handler_data
        return bool(data.get("project_id") and data.get("issue_identifiers"))

    async def deliver(self, task: Task) -> dict:
        # Commit and push the spec frontmatter bump directly to main.
        repo_path = task.handler_data.get("repo_path")
        spec_rel = task.handler_data.get("spec_path")
        if not repo_path or not spec_rel:
            return {"status": "delivered", "error": "missing repo or spec path"}

        try:
            # Verify the diff is allowlisted before committing
            changed = await self._git.get_changed_files(repo_path, base_branch="HEAD")
            violation = check_handler_allowlist(
                handler=self.task_type,
                repo=self._self_repo,
                changed_files=changed,
            )
            if violation:
                raise RuntimeError(violation)

            await self._git.commit_all(repo_path, f"chore: mark {spec_rel} executing")
            await self._git._run("git push origin HEAD:main", cwd=repo_path)
        except RuntimeError as e:
            logger.error(f"tickets deliver failed: {e}")
            return {"status": "delivered", "error": str(e)}

        return {
            "status": "delivered",
            "project_url": task.handler_data.get("project_url"),
            "issue_count": len(task.handler_data.get("issue_identifiers", [])),
        }
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_tickets_handler.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/handlers/tickets.py tests/test_tickets_handler.py
git commit -m "feat(tickets): create Linear project+issues, bump spec to executing"
```

---

## Task 13: Plan-merge watcher

**Files:**
- Create: `forge/watchers/plan_merge_watcher.py`
- Test: `tests/test_plan_merge_watcher.py`

Detection rule: in the AF repo clone, a spec with `status: planned` that has a corresponding plan file existing on main, and no tickets task has been enqueued for this plan yet (dedupe by `source_id = f"plan:{plan_path}"`). This avoids needing GitHub PR-state API calls; the plan is considered "merged" once the plan file exists on the main branch alongside the planned-status spec.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_plan_merge_watcher.py
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from forge.models import TaskType
from forge.watchers.plan_merge_watcher import PlanMergeWatcher


class FakeStore:
    def __init__(self):
        self.saved = []
        self.existing_ids: set[str] = set()

    async def find_by_source_id(self, sid):
        return "exists" if sid in self.existing_ids else None

    async def save(self, task):
        self.saved.append(task)


async def test_enqueues_tickets_when_plan_and_planned_spec_present(tmp_path: Path):
    repo = tmp_path / "repo"
    plans = repo / "docs" / "superpowers" / "plans"
    specs = repo / "docs" / "superpowers" / "specs"
    plans.mkdir(parents=True)
    specs.mkdir(parents=True)
    (plans / "2026-04-15-foo.md").write_text("# Plan\n## Task 1: x\n\nbody\n")
    (specs / "2026-04-15-foo.md").write_text("---\nstatus: planned\n---\n\nbody\n")

    store = FakeStore()
    watcher = PlanMergeWatcher(
        store=store,
        repo_path=str(repo),
        fetch_fn=AsyncMock(),
    )
    created = await watcher.poll()
    assert created == 1
    task = store.saved[0]
    assert task.type == TaskType.TICKETS
    assert "plan: docs/superpowers/plans/2026-04-15-foo.md" in task.description
    assert "spec: docs/superpowers/specs/2026-04-15-foo.md" in task.description


async def test_skips_when_no_matching_spec(tmp_path: Path):
    repo = tmp_path / "repo"
    plans = repo / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / "2026-04-15-foo.md").write_text("# Plan\n")
    store = FakeStore()
    watcher = PlanMergeWatcher(store=store, repo_path=str(repo), fetch_fn=AsyncMock())
    created = await watcher.poll()
    assert created == 0


async def test_deduplicates(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (repo / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (repo / "docs" / "superpowers" / "plans" / "2026-04-15-foo.md").write_text("# P\n")
    (repo / "docs" / "superpowers" / "specs" / "2026-04-15-foo.md").write_text(
        "---\nstatus: planned\n---\n\n"
    )
    store = FakeStore()
    store.existing_ids.add("plan:docs/superpowers/plans/2026-04-15-foo.md")
    watcher = PlanMergeWatcher(store=store, repo_path=str(repo), fetch_fn=AsyncMock())
    assert await watcher.poll() == 0
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_plan_merge_watcher.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# forge/watchers/plan_merge_watcher.py
import logging
from pathlib import Path
from typing import Awaitable, Callable

from forge.frontmatter import SpecStatus, read_spec
from forge.models import Task, TaskSource, TaskType

logger = logging.getLogger(__name__)


class PlanMergeWatcher:
    def __init__(
        self,
        store,
        repo_path: str,
        plans_subdir: str = "docs/superpowers/plans",
        specs_subdir: str = "docs/superpowers/specs",
        fetch_fn: Callable[[], Awaitable[None]] | None = None,
        self_repo: str = "t-eckert/ardent-forge",
    ):
        self._store = store
        self._repo_path = Path(repo_path)
        self._plans_subdir = plans_subdir
        self._specs_subdir = specs_subdir
        self._fetch = fetch_fn
        self._self_repo = self_repo

    async def poll(self) -> int:
        if self._fetch:
            try:
                await self._fetch()
            except Exception:
                logger.exception("plan-merge watcher fetch failed")

        plans_dir = self._repo_path / self._plans_subdir
        specs_dir = self._repo_path / self._specs_subdir
        if not plans_dir.is_dir() or not specs_dir.is_dir():
            return 0

        created = 0
        for plan_abs in sorted(plans_dir.glob("*.md")):
            spec_abs = specs_dir / plan_abs.name
            if not spec_abs.exists():
                continue
            parsed = read_spec(spec_abs)
            if parsed.status != SpecStatus.PLANNED:
                continue

            plan_rel = str(plan_abs.relative_to(self._repo_path))
            spec_rel = str(spec_abs.relative_to(self._repo_path))
            source_id = f"plan:{plan_rel}"
            if await self._store.find_by_source_id(source_id) is not None:
                continue

            task = Task.new(
                task_type=TaskType.TICKETS,
                source=TaskSource.WEBHOOK,
                title=f"tickets for {plan_abs.stem}",
                description=f"plan: {plan_rel} spec: {spec_rel}",
                source_id=source_id,
                repo=self._self_repo,
            )
            await self._store.save(task)
            logger.info(f"Enqueued tickets task for {plan_rel}")
            created += 1
        return created
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_plan_merge_watcher.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/watchers/plan_merge_watcher.py tests/test_plan_merge_watcher.py
git commit -m "feat(watchers): plan-merge watcher enqueues tickets tasks"
```

---

## Task 14: Wire watchers into the coordinator tick

**Files:**
- Modify: `forge/coordinator.py`
- Test: extend `tests/test_coordinator.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_coordinator.py`:

```python
async def test_coordinator_calls_extra_watchers_in_tick():
    from unittest.mock import AsyncMock
    from forge.coordinator import Coordinator
    from forge.handlers import HandlerRegistry

    class FakeStore:
        async def list_pending(self, limit): return []
        async def reset_active_tasks(self): return 0

    store = FakeStore()
    registry = HandlerRegistry()
    w1 = AsyncMock(); w1.poll = AsyncMock(return_value=2)
    w2 = AsyncMock(); w2.poll = AsyncMock(return_value=0)

    coord = Coordinator(store=store, registry=registry, watchers=[w1, w2])
    await coord.tick()
    w1.poll.assert_awaited_once()
    w2.poll.assert_awaited_once()
```

- [ ] **Step 2: Update `Coordinator` to accept `watchers`**

In `forge/coordinator.py`:

```python
class Coordinator:
    def __init__(
        self,
        store: TaskStore,
        registry: HandlerRegistry,
        max_concurrent: int = 2,
        poller=None,
        watchers: list | None = None,
    ):
        self._store = store
        self._registry = registry
        self._max_concurrent = max_concurrent
        self._poller = poller
        self._watchers = watchers or []

    async def tick(self) -> int:
        if self._poller:
            try:
                created = await self._poller.poll()
                if created > 0:
                    logger.info(f"Ingested {created} tasks from Linear")
            except Exception:
                logger.exception("Error polling Linear")

        for watcher in self._watchers:
            try:
                n = await watcher.poll()
                if n > 0:
                    logger.info(f"Watcher {watcher.__class__.__name__} enqueued {n} tasks")
            except Exception:
                logger.exception(f"Error in watcher {watcher.__class__.__name__}")

        return await self.process_pending()
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_coordinator.py -v`
Expected: all PASS (existing + new).

- [ ] **Step 4: Commit**

```bash
git add forge/coordinator.py tests/test_coordinator.py
git commit -m "feat(coordinator): accept extra watchers and poll them each tick"
```

---

## Task 15: Register plan + tickets handlers and watchers in main.py

**Files:**
- Modify: `forge/main.py`
- Modify: `forge/config.py`

- [ ] **Step 1: Add config fields**

In `forge/config.py`:

```python
    # Self-building loop
    self_repo: str = "t-eckert/ardent-forge"
    self_repo_url: str = "https://github.com/t-eckert/ardent-forge.git"
    planner_claude_model: str = "claude-opus-4-20250514"
```

- [ ] **Step 2: Register handlers and watchers in main.py lifespan**

In `forge/main.py`, after the existing handler registrations and before `coordinator = Coordinator(...)`:

```python
        # Self-building: plan + tickets handlers, watchers
        from forge.handlers.plan import PlanHandler
        from forge.handlers.tickets import TicketsHandler
        from forge.linear.projects import LinearProjectsAPI
        from forge.watchers.spec_watcher import SpecWatcher
        from forge.watchers.plan_merge_watcher import PlanMergeWatcher
        from forge.git import GitOps as _GitOps

        registry.register(
            PlanHandler(
                workspace_dir=settings.workspace_dir,
                self_repo=settings.self_repo,
                claude_model=settings.planner_claude_model,
            )
        )

        watchers: list = []
        if settings.linear_api_key and settings.linear_team_id:
            tickets_linear = LinearProjectsAPI(linear_client)
            registry.register(
                TicketsHandler(
                    workspace_dir=settings.workspace_dir,
                    linear=tickets_linear,
                    team_id=settings.linear_team_id,
                    self_repo=settings.self_repo,
                )
            )

        # Ensure AF repo clone exists for the watchers to scan
        af_git = _GitOps(settings.workspace_dir)
        af_repo_path = await af_git.ensure_repo(settings.self_repo_url, settings.self_repo)

        async def _fetch_main() -> None:
            await af_git._run("git fetch origin main", cwd=af_repo_path)
            await af_git._run("git checkout main", cwd=af_repo_path)
            await af_git._run("git reset --hard origin/main", cwd=af_repo_path)

        watchers.append(
            SpecWatcher(
                store=store,
                repo_path=af_repo_path,
                fetch_fn=_fetch_main,
                self_repo=settings.self_repo,
            )
        )
        watchers.append(
            PlanMergeWatcher(
                store=store,
                repo_path=af_repo_path,
                fetch_fn=_fetch_main,
                self_repo=settings.self_repo,
            )
        )
```

Then pass `watchers=watchers` to the `Coordinator(...)` constructor.

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: all tests PASS; no regressions.

- [ ] **Step 4: Smoke check — server starts**

Run: `uv run forge` (or equivalent), with `FORGE_LINEAR_API_KEY` and `FORGE_LINEAR_TEAM_ID` set to dummy values if needed to exercise the code path. Confirm no startup crash. Stop.

- [ ] **Step 5: Commit**

```bash
git add forge/main.py forge/config.py
git commit -m "feat(main): register plan+tickets handlers and self-building watchers"
```

---

## Task 16: End-to-end integration smoke test

**Files:**
- Create: `tests/test_bootstrap_integration.py`

Simulate the full loop in-process: a fake AF repo with a `ready-to-plan` spec → SpecWatcher enqueues plan task → a stub PlanHandler writes a plan file and bumps spec → PlanMergeWatcher enqueues tickets task → TicketsHandler (with mocked LinearProjectsAPI) creates project+issues and bumps spec to `executing`.

This exercises the wiring, not the real Claude or Linear calls.

- [ ] **Step 1: Write test**

```python
# tests/test_bootstrap_integration.py
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from forge.frontmatter import SpecStatus, read_spec, update_spec_status
from forge.handlers.tickets import TicketsHandler
from forge.watchers.plan_merge_watcher import PlanMergeWatcher
from forge.watchers.spec_watcher import SpecWatcher


class InMemStore:
    def __init__(self):
        self.tasks = []

    async def find_by_source_id(self, sid):
        for t in self.tasks:
            if t.source_id == sid:
                return t
        return None

    async def save(self, task):
        self.tasks.append(task)


async def test_full_bootstrap_loop(tmp_path: Path):
    # Seed repo
    repo = tmp_path / "repo"
    plans = repo / "docs" / "superpowers" / "plans"
    specs = repo / "docs" / "superpowers" / "specs"
    plans.mkdir(parents=True)
    specs.mkdir(parents=True)
    spec_file = specs / "2026-04-15-foo.md"
    spec_file.write_text("---\nstatus: ready-to-plan\ntitle: Foo\n---\n\nBody\n")

    store = InMemStore()

    spec_watcher = SpecWatcher(
        store=store, repo_path=str(repo), fetch_fn=AsyncMock()
    )
    plan_merge_watcher = PlanMergeWatcher(
        store=store, repo_path=str(repo), fetch_fn=AsyncMock()
    )

    # 1. Spec watcher sees ready-to-plan, enqueues plan task
    assert await spec_watcher.poll() == 1
    assert store.tasks[0].type == "plan"

    # 2. Simulate plan handler writing a plan and bumping spec
    plan_file = plans / "2026-04-15-foo.md"
    plan_file.write_text("# Foo Plan\n\n## Task 1: First\n\nbody1\n\n## Task 2: Second\n\nbody2\n")
    update_spec_status(spec_file, SpecStatus.PLANNED)

    # 3. Plan-merge watcher sees the plan + planned spec, enqueues tickets
    assert await plan_merge_watcher.poll() == 1
    tickets_task = store.tasks[-1]
    assert tickets_task.type == "tickets"

    # 4. Tickets handler executes with mocked Linear
    linear = AsyncMock()
    linear.create_project = AsyncMock(return_value=("p1", "url"))
    linear.get_label_id = AsyncMock(return_value="lab")
    linear.create_issue = AsyncMock(side_effect=[
        ("i1", "FORGE-1", "u1"),
        ("i2", "FORGE-2", "u2"),
    ])
    handler = TicketsHandler(
        workspace_dir=str(tmp_path / "ws"),
        linear=linear,
        team_id="t1",
    )
    handler._git.ensure_repo = AsyncMock(return_value=str(repo))
    result = await handler.execute(tickets_task)

    assert result["issue_identifiers"] == ["FORGE-1", "FORGE-2"]
    assert read_spec(spec_file).status == SpecStatus.EXECUTING

    # 5. Re-polling does not duplicate
    assert await spec_watcher.poll() == 0
    assert await plan_merge_watcher.poll() == 0
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_bootstrap_integration.py -v`
Expected: PASS.

- [ ] **Step 3: Full suite run**

Run: `uv run pytest`
Expected: all prior tests still pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_bootstrap_integration.py
git commit -m "test(bootstrap): end-to-end self-building loop smoke"
```

---

## Task 17: Self-referential validation — use Phase 0 to plan Phase A1

**Files:** (none in this repo beyond a new spec)

This is the real acceptance test: once Phase 0 is deployed, the first spec Ardent Forge plans is A1 (multi-repo support from the roadmap).

- [ ] **Step 1: Write the A1 spec**

Create `docs/superpowers/specs/YYYY-MM-DD-code-multirepo.md` with frontmatter `status: draft` and a short spec for Track A1 from the roadmap.

- [ ] **Step 2: Flip to ready-to-plan, push**

Edit frontmatter to `status: ready-to-plan`, commit, push to main.

- [ ] **Step 3: Observe loop**

Within one tick interval: spec watcher enqueues a plan task; plan handler produces a plan PR; review and merge; plan-merge watcher enqueues a tickets task; Linear project and issues appear.

- [ ] **Step 4: Observe execution**

Existing Linear poller picks up the new devagent-labeled issues; code handler executes them; PRs appear. Merge in order.

- [ ] **Step 5: Record outcome in the log**

Append a note to today's `~/Notebook/Log/YYYY-MM-DD.md` describing what worked and any friction observed. This data shapes future phases.

---

## Success Criteria

Phase 0 is complete when:

1. All automated tests (Tasks 1–16) pass.
2. A spec with `status: ready-to-plan` on AF's main branch produces a plan PR within one coordinator tick interval, with no human intervention before PR open.
3. Merging the plan PR produces a Linear Project with one `devagent`-labeled issue per numbered plan task.
4. The spec frontmatter transitions accurately through `ready-to-plan → planned → executing` as the loop progresses.
5. Guardrails prevent the `plan` handler from producing a diff outside `docs/superpowers/plans/` and `docs/superpowers/specs/` frontmatter, verified by verify-step rejection.
6. Task 17 is complete: A1 was planned by AF itself.
