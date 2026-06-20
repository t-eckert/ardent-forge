# Phase 2b — Follow-up Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an operator follow up on a finished Code task with a queued continuation run that reuses the parent's git worktree and Claude conversation (`claude --continue`), reclaiming worktrees with an age-based reaper instead of deleting them at delivery.

**Architecture:** Add `continues_task_id` to the task model. `deliver()` stops removing the worktree; a reference-aware reaper on the coordinator tick reclaims worktrees once all referencing tasks are terminal and older than a TTL. The Code agent's `execute` reuses the parent worktree and passes a `continue_session` flag to `ZellijRunner`. Delivery becomes PR-idempotent (update the existing PR instead of erroring). A new `POST /api/tasks/{id}/follow-up` endpoint creates the linked continuation task.

**Tech Stack:** Python 3.13, FastAPI, async SQLite (aiosqlite), Pydantic v2, pytest + pytest-asyncio (`asyncio_mode = "auto"`).

**Spec:** `docs/superpowers/specs/2026-06-19-control-plane-phase2b-followup-continuation-design.md`

---

## File Structure

**Modified:**
- `forge/models.py` — add `continues_task_id` field, `new()` param, `to_row`/`from_row`.
- `forge/db.py` — schema column + idempotent migration.
- `forge/zellij/runner.py` — `continue_session` param on `run` + both run paths.
- `forge/claude.py` — `build_followup_prompt(prompt)` helper.
- `forge/git.py` — `get_existing_pr_url`, `push_branch`, `prune_worktrees` helpers.
- `forge/agents/code.py` — PR-idempotent `deliver` (drop `cleanup_worktree`); follow-up-aware `execute`.
- `forge/store.py` — `list_tasks_with_worktrees()`.
- `forge/coordinator.py` — `git` constructor param, `reap_old_worktrees()`, tick wiring.
- `forge/config.py` — `worktree_ttl_hours` setting.
- `forge/api/tasks.py` — `POST /{task_id}/follow-up`.
- `forge/main.py` — pass `git=GitOps(...)` to the coordinator.

**Created:**
- `forge/worktree_reaper.py` — pure `reapable_worktrees(...)` decision function.
- `tests/test_worktree_reaper.py`, plus additions to `tests/test_db.py`, `tests/test_zellij_runner.py`, `tests/test_git.py`, `tests/test_code_handler.py`, `tests/test_coordinator_steering.py`, `tests/test_api_steering.py`.

---

### Task 1: `continues_task_id` on the task model + DB

**Files:**
- Modify: `forge/models.py:53` (field), `forge/models.py:59-82` (`new`), `forge/models.py:84-108` (`to_row`), `forge/models.py:110-143` (`from_row`)
- Modify: `forge/db.py:19` (schema), `forge/db.py:68-73` (migrations)
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_db.py`:

```python
async def test_continues_task_id_roundtrip(store):
    from forge.models import Task, TaskSource, TaskType

    parent = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="p", description="d")
    await store.save(parent)
    child = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.MANUAL,
        title="c",
        description="follow up",
        continues_task_id=parent.id,
    )
    await store.save(child)

    loaded = await store.get(child.id)
    assert loaded.continues_task_id == parent.id

    # Default is None for a non-follow-up task.
    loaded_parent = await store.get(parent.id)
    assert loaded_parent.continues_task_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_db.py::test_continues_task_id_roundtrip -v`
Expected: FAIL — `Task.new()` got an unexpected keyword argument `continues_task_id` (or `AttributeError`).

- [ ] **Step 3: Add the model field**

In `forge/models.py`, add after the `require_approval` field (line 53):

```python
    require_approval: bool = False
    continues_task_id: str | None = None
```

- [ ] **Step 4: Add the `new()` parameter**

In `forge/models.py`, add the parameter to `new()` (after `require_approval: bool = False,` at line 67) and pass it through:

```python
        require_approval: bool = False,
        continues_task_id: str | None = None,
    ) -> "Task":
        now = datetime.now(timezone.utc)
        return cls(
            id=str(ulid.new()),
            type=task_type,
            status=TaskStatus.QUEUED,
            source=source,
            source_id=source_id,
            repo=repo,
            title=title,
            description=description,
            require_approval=require_approval,
            continues_task_id=continues_task_id,
            created_at=now,
            updated_at=now,
        )
```

- [ ] **Step 5: Persist in `to_row` / read in `from_row`**

In `forge/models.py` `to_row`, add after the `require_approval` line (line 102):

```python
            "require_approval": int(self.require_approval),
            "continues_task_id": self.continues_task_id,
```

In `from_row`, add after the `require_approval` line (line 135):

```python
            require_approval=bool(row.get("require_approval", 0)),
            continues_task_id=row.get("continues_task_id"),
```

- [ ] **Step 6: Add the DB column + migration**

In `forge/db.py`, add the column to the `tasks` CREATE TABLE after `require_approval` (line 19):

```python
    require_approval INTEGER NOT NULL DEFAULT 0,
    continues_task_id TEXT,
```

And add the idempotent migration to the `for alter in (...)` tuple (after line 72):

```python
            "ALTER TABLE tasks ADD COLUMN require_approval INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE tasks ADD COLUMN continues_task_id TEXT",
```

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest tests/test_db.py::test_continues_task_id_roundtrip -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add forge/models.py forge/db.py tests/test_db.py
git commit -m "feat(model): continues_task_id for follow-up tasks"
```

---

### Task 2: `ZellijRunner.continue_session` flag

**Files:**
- Modify: `forge/zellij/runner.py:29-52` (`run`), `forge/zellij/runner.py:54-77` (`_run_direct`), `forge/zellij/runner.py:79-118` (`_run_in_zellij`)
- Test: `tests/test_zellij_runner.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_zellij_runner.py`:

```python
import asyncio
from unittest.mock import patch
from forge.zellij.runner import ZellijRunner


async def test_continue_session_adds_continue_flag(monkeypatch):
    captured = {}

    class FakeProc:
        returncode = 0

        async def communicate(self):
            return (b"ok", b"")

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        return FakeProc()

    # Force the direct path (no zellij) and capture the claude argv.
    monkeypatch.setattr(ZellijRunner, "available", staticmethod(lambda: False))
    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        runner = ZellijRunner(model="sonnet", timeout=5)
        await runner.run("hi", "/tmp", session_name="agent-x", continue_session=True)

    assert "--continue" in captured["args"]


async def test_no_continue_flag_by_default(monkeypatch):
    captured = {}

    class FakeProc:
        returncode = 0

        async def communicate(self):
            return (b"ok", b"")

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        return FakeProc()

    monkeypatch.setattr(ZellijRunner, "available", staticmethod(lambda: False))
    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        runner = ZellijRunner(model="sonnet", timeout=5)
        await runner.run("hi", "/tmp", session_name="agent-x")

    assert "--continue" not in captured["args"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_zellij_runner.py::test_continue_session_adds_continue_flag -v`
Expected: FAIL — `run()` got an unexpected keyword argument `continue_session`.

- [ ] **Step 3: Thread the flag through `run`**

In `forge/zellij/runner.py`, update the `run` signature (line 29) and both call sites:

```python
    async def run(
        self,
        prompt: str,
        work_dir: str,
        session_name: str | None = None,
        extra_env: dict[str, str] | None = None,
        continue_session: bool = False,
    ) -> str:
```

Then change the two dispatch calls inside `run`:

```python
        if session_name and self.available():
            logger.info("Running Claude in Zellij session %s (cwd=%s)", session_name, work_dir)
            return await self._run_in_zellij(prompt, work_dir, session_name, env, continue_session)

        if session_name:
            logger.info("zellij not available; running Claude directly (session=%s)", session_name)
        return await self._run_direct(prompt, work_dir, env, continue_session)
```

- [ ] **Step 4: Add the flag to `_run_direct`**

Replace `_run_direct` (lines 54-77) so the argv is built with an optional `--continue`:

```python
    async def _run_direct(
        self, prompt: str, work_dir: str, env: dict, continue_session: bool = False
    ) -> str:
        argv = ["claude", "--print", "--dangerously-skip-permissions", "--model", self._model]
        if continue_session:
            argv.append("--continue")
        argv += ["-p", prompt]
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=work_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise TimeoutError(f"Claude Code timed out after {self._timeout}s")
        output = stdout.decode()
        if proc.returncode != 0:
            error = stderr.decode().strip() or output.strip() or "(no output)"
            logger.error("Claude Code failed (rc=%d): %s", proc.returncode, error)
            raise RuntimeError(f"Claude Code failed: {error}")
        return output
```

- [ ] **Step 5: Add the flag to `_run_in_zellij`**

In `forge/zellij/runner.py`, update the `_run_in_zellij` signature (line 79) to accept `continue_session: bool = False`, and build the claude argv inside the generated runner code conditionally. Replace the `subprocess.run([...])` argv (lines 103-110) with:

```python
        continue_arg = "'--continue', " if continue_session else ""
        runner_code = textwrap.dedent(f"""\
            import subprocess, pathlib, os

            prompt = pathlib.Path({str(prompt_file)!r}).read_text()
            env = dict(os.environ)
            forge_key = env.get('FORGE_ANTHROPIC_API_KEY', '')
            if forge_key and 'ANTHROPIC_API_KEY' not in env:
                env['ANTHROPIC_API_KEY'] = forge_key
            env['CLAUDE_NO_TELEMETRY'] = '1'

            result = subprocess.run(
                ['claude', '--print', '--dangerously-skip-permissions',
                 '--model', {self._model!r}, {continue_arg}'-p', prompt],
                cwd={work_dir!r},
                capture_output=True,
                text=True,
                env=env,
            )

            out = result.stdout
            if result.returncode != 0:
                out += result.stderr
            pathlib.Path({str(output_file)!r}).write_text(out)
            pathlib.Path({str(exit_file)!r}).write_text(str(result.returncode))
        """)
```

Update the signature line:

```python
    async def _run_in_zellij(
        self, prompt: str, work_dir: str, session_name: str, env: dict, continue_session: bool = False
    ) -> str:
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_zellij_runner.py -v`
Expected: PASS (both new tests + existing ones).

- [ ] **Step 7: Commit**

```bash
git add forge/zellij/runner.py tests/test_zellij_runner.py
git commit -m "feat(zellij): continue_session flag adds --continue"
```

---

### Task 3: GitOps PR-idempotency + prune helpers

**Files:**
- Modify: `forge/git.py` (add three methods after `create_pr`, near line 98)
- Test: `tests/test_git.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_git.py`:

```python
from unittest.mock import AsyncMock
from forge.git import GitOps


async def test_get_existing_pr_url_returns_url():
    git = GitOps("/tmp")
    git._run = AsyncMock(return_value="https://github.com/o/r/pull/7\n")
    url = await git.get_existing_pr_url("/wt")
    assert url == "https://github.com/o/r/pull/7"


async def test_get_existing_pr_url_none_when_no_pr():
    git = GitOps("/tmp")
    git._run = AsyncMock(side_effect=RuntimeError("no pull requests found"))
    url = await git.get_existing_pr_url("/wt")
    assert url is None


async def test_push_branch_pushes_current_branch():
    git = GitOps("/tmp")
    calls = []

    async def fake_run(cmd, cwd=None):
        calls.append(cmd)
        if cmd[:2] == ["git", "rev-parse"]:
            return "forge/abc\n"
        return ""

    git._run = fake_run
    await git.push_branch("/wt")
    assert ["git", "push", "-u", "origin", "forge/abc"] in calls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_git.py::test_get_existing_pr_url_returns_url -v`
Expected: FAIL — `GitOps` has no attribute `get_existing_pr_url`.

- [ ] **Step 3: Add the helpers**

In `forge/git.py`, add after `create_pr` (after line 98):

```python
    async def get_existing_pr_url(self, worktree_path: str) -> str | None:
        """Return the URL of an open PR for the worktree's current branch, or
        None when there is no PR. `gh pr view` exits non-zero (RuntimeError) when
        the branch has no associated PR."""
        try:
            out = await self._run(
                ["gh", "pr", "view", "--json", "url", "-q", ".url"],
                cwd=worktree_path,
            )
        except RuntimeError:
            return None
        url = out.strip()
        return url or None

    async def push_branch(self, worktree_path: str) -> None:
        """Push the worktree's current branch to origin (updates an open PR)."""
        branch = (
            await self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=worktree_path)
        ).strip()
        await self._run(["git", "push", "-u", "origin", branch], cwd=worktree_path)

    async def prune_worktrees(self, repo_path: str) -> None:
        """Drop stale worktree registrations after a removal."""
        await self._run(["git", "worktree", "prune"], cwd=repo_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_git.py -k "pr_url or push_branch" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add forge/git.py tests/test_git.py
git commit -m "feat(git): existing-PR lookup, push_branch, prune_worktrees helpers"
```

---

### Task 4: PR-idempotent deliver (drop worktree cleanup)

**Files:**
- Modify: `forge/agents/code.py:136-175` (`deliver`)
- Test: `tests/test_code_handler.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_code_handler.py`:

```python
from types import SimpleNamespace


class _FakeGit:
    def __init__(self, existing_pr=None):
        self._existing_pr = existing_pr
        self.created = False
        self.pushed = False
        self.cleaned = False

    async def get_diff(self, worktree_path, base):
        return "diff"

    async def get_existing_pr_url(self, worktree_path):
        return self._existing_pr

    async def push_branch(self, worktree_path):
        self.pushed = True

    async def create_pr(self, worktree_path, title, body):
        self.created = True
        return "https://github.com/o/r/pull/1"

    async def cleanup_worktree(self, repo_path, worktree_path):
        self.cleaned = True


def _delivery_task(tmp_path):
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d", repo="o/r")
    task.handler_data = {
        "worktree_path": str(tmp_path),
        "repo_path": str(tmp_path),
        "branch_name": "forge/abc",
    }
    return task


async def test_deliver_updates_existing_pr_and_keeps_worktree(handler, tmp_path):
    fake = _FakeGit(existing_pr="https://github.com/o/r/pull/9")
    handler._git = fake
    task = _delivery_task(tmp_path)
    result = await handler.deliver(task, ctx)
    assert result["pr_url"] == "https://github.com/o/r/pull/9"
    assert fake.pushed is True
    assert fake.created is False
    assert fake.cleaned is False  # worktree is no longer cleaned up at deliver


async def test_deliver_creates_pr_when_none_exists(handler, tmp_path):
    fake = _FakeGit(existing_pr=None)
    handler._git = fake
    task = _delivery_task(tmp_path)
    result = await handler.deliver(task, ctx)
    assert result["pr_url"] == "https://github.com/o/r/pull/1"
    assert fake.created is True
    assert fake.cleaned is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_code_handler.py::test_deliver_updates_existing_pr_and_keeps_worktree -v`
Expected: FAIL — current `deliver` calls `get_diff` then `create_pr` unconditionally and calls `cleanup_worktree` (AttributeError on `get_existing_pr_url`, or `fake.cleaned` True).

- [ ] **Step 3: Rewrite the PR + cleanup block in `deliver`**

In `forge/agents/code.py`, replace the block from `try:` / `pr_url = await self._git.create_pr(...)` through the `cleanup_worktree` try/except (lines 160-169) with:

```python
        existing = await self._git.get_existing_pr_url(worktree_path)
        if existing:
            try:
                await self._git.push_branch(worktree_path)
            except RuntimeError as e:
                logger.warning("Failed to push follow-up commits for %s: %s", task.id, e)
            pr_url = existing
        else:
            try:
                pr_url = await self._git.create_pr(worktree_path, title, body)
            except RuntimeError as e:
                logger.error("PR creation failed: %s", e)
                pr_url = f"PR creation failed: {e}"

        # NB: the worktree is intentionally NOT cleaned up here. Worktrees persist
        # after delivery so follow-up tasks can `claude --continue` in them; the
        # coordinator's worktree reaper reclaims them once all referencing tasks
        # are terminal and past the TTL.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_code_handler.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add forge/agents/code.py tests/test_code_handler.py
git commit -m "feat(code): PR-idempotent deliver; stop cleaning up worktree at delivery"
```

---

### Task 5: Follow-up-aware execute

**Files:**
- Modify: `forge/claude.py` (add `build_followup_prompt`)
- Modify: `forge/agents/code.py:1-8` (imports), `forge/agents/code.py:66-117` (`execute`)
- Test: `tests/test_code_handler.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_code_handler.py`:

```python
async def test_followup_reuses_parent_worktree_and_continues(db, tmp_path):
    store = TaskStore(db)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    parent_wt = tmp_path / "parent-wt"
    parent_wt.mkdir()

    h = CodeAgent(workspace_dir=str(workspace))

    parent = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="p", description="d", repo="o/r")
    await store.save(parent)
    await store.update_handler_data(parent.id, {
        "worktree_path": str(parent_wt),
        "repo_path": str(tmp_path / "repo"),
        "branch_name": "forge/parent",
    })

    child = Task.new(
        task_type=TaskType.CODE, source=TaskSource.MANUAL, title="c",
        description="also add logging", repo="o/r", continues_task_id=parent.id,
    )
    await store.save(child)

    calls = {}

    async def fake_run(prompt, work_dir, session_name=None, continue_session=False):
        calls["work_dir"] = work_dir
        calls["continue_session"] = continue_session
        return "done"

    h._zellij.run = fake_run
    h._git.create_worktree = AsyncMock(side_effect=AssertionError("must not create a worktree for a follow-up"))

    vctx = AgentContext(tools=[], store=store, settings=None)
    result = await h.execute(await store.get(child.id), vctx)

    assert calls["work_dir"] == str(parent_wt)
    assert calls["continue_session"] is True
    assert result["worktree_path"] == str(parent_wt)
    assert result["branch_name"] == "forge/parent"


async def test_followup_missing_worktree_raises(db, tmp_path):
    store = TaskStore(db)
    workspace = tmp_path / "ws2"
    workspace.mkdir()
    h = CodeAgent(workspace_dir=str(workspace))

    parent = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="p", description="d", repo="o/r")
    await store.save(parent)
    await store.update_handler_data(parent.id, {"worktree_path": str(tmp_path / "gone")})

    child = Task.new(
        task_type=TaskType.CODE, source=TaskSource.MANUAL, title="c",
        description="x", repo="o/r", continues_task_id=parent.id,
    )
    await store.save(child)

    vctx = AgentContext(tools=[], store=store, settings=None)
    with pytest.raises(RuntimeError):
        await h.execute(await store.get(child.id), vctx)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_code_handler.py::test_followup_reuses_parent_worktree_and_continues -v`
Expected: FAIL — current `execute` ignores `continues_task_id`, calls `create_worktree` (triggers the AssertionError) and does not pass `continue_session`.

- [ ] **Step 3: Add the follow-up prompt builder**

In `forge/claude.py`, add after `build_prompt` (after line 34):

```python
def build_followup_prompt(prompt: str) -> str:
    parts = [
        "# Follow-up",
        "\nThis continues your previous session in this repository. The prior "
        "conversation and your working tree are intact — build on the work "
        "already done.",
        f"\n## Request\n{prompt}",
        "\n## Instructions"
        "\n- Build on the work already done in this session"
        "\n- Write or update tests as appropriate"
        "\n- Run the project's build and test commands to verify your work"
        "\n- Commit your changes with a clear commit message",
    ]
    return "\n".join(parts)
```

- [ ] **Step 4: Rewrite `execute` to branch on `continues_task_id`**

In `forge/agents/code.py`, update imports (line 4):

```python
from forge.claude import build_followup_prompt, build_prompt
```

Add `import os` at the top (line 1, before `import logging`):

```python
import logging
import os
```

Replace `execute` (lines 66-117) with:

```python
    async def execute(self, task: Task, ctx: AgentContext) -> dict:
        session_name = f"agent-{task.id}"

        # Persist the session name before the long-running Claude run so that a
        # timeout/reap can tear down the orphaned session (the result dict below
        # is only written back to the store *after* execute completes).
        await ctx.store.update_handler_data(task.id, {"zellij_session": session_name})

        if task.continues_task_id:
            parent = await ctx.store.get(task.continues_task_id)
            if parent is None:
                raise RuntimeError(
                    f"Follow-up parent {task.continues_task_id} not found for task {task.id}"
                )
            pdata = parent.handler_data or {}
            worktree_path = pdata.get("worktree_path")
            repo_path = pdata.get("repo_path", "")
            branch_name = pdata.get("branch_name", "")
            if not worktree_path or not os.path.isdir(worktree_path):
                raise RuntimeError(
                    f"Parent worktree unavailable for follow-up {task.id} "
                    f"(path={worktree_path!r}); it may have been reaped"
                )
            base_prompt = build_followup_prompt(task.description)
            continue_session = True
        else:
            repo_url = f"https://github.com/{task.repo}.git"
            branch_name = f"forge/{task.id[:12]}"
            repo_path = await self._git.ensure_repo(repo_url, task.repo)
            worktree_path = await self._git.create_worktree(repo_path, branch_name)
            base_prompt = build_prompt(
                title=task.title, description=task.description, repo=task.repo
            )
            continue_session = False

        retry_context = None
        output = ""

        for attempt in range(MAX_RETRIES + 1):
            run_prompt = base_prompt
            if retry_context:
                run_prompt = f"{base_prompt}\n\n## Previous Attempt Context\n{retry_context}"
                logger.info("Retry %d/%d for task %s", attempt, MAX_RETRIES, task.id)

            try:
                output = await self._zellij.run(
                    run_prompt,
                    worktree_path,
                    session_name=session_name,
                    continue_session=continue_session,
                )
            except (TimeoutError, RuntimeError) as e:
                retry_context = f"Attempt {attempt + 1} failed: {e}"
                if attempt == MAX_RETRIES:
                    raise
                continue

            break

        return {
            "worktree_path": worktree_path,
            "repo_path": repo_path,
            "branch_name": branch_name,
            "claude_output": output[:2000],
            "zellij_session": session_name,
            "attach_cmd": f"ssh box -t zellij attach {session_name}",
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_code_handler.py tests/test_claude.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add forge/agents/code.py forge/claude.py tests/test_code_handler.py
git commit -m "feat(code): follow-up execute reuses parent worktree + --continue"
```

---

### Task 6: Worktree reaper

**Files:**
- Create: `forge/worktree_reaper.py`
- Modify: `forge/store.py` (add `list_tasks_with_worktrees`)
- Modify: `forge/coordinator.py:31-60` (`__init__`), `forge/coordinator.py:119-124` (tick wiring), add `reap_old_worktrees`
- Modify: `forge/config.py:18` (add setting)
- Modify: `forge/main.py:268-276` (pass `git`)
- Test: `tests/test_worktree_reaper.py`, `tests/test_coordinator_steering.py`

- [ ] **Step 1: Write the failing test for the pure decision function**

Create `tests/test_worktree_reaper.py`:

```python
from datetime import datetime, timedelta, timezone

from forge.models import Task, TaskSource, TaskStatus, TaskType
from forge.worktree_reaper import reapable_worktrees


def _task(status, updated_at, worktree_path, repo_path="/repo"):
    t = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d")
    t = t.model_copy(update={
        "status": status,
        "updated_at": updated_at,
        "handler_data": {"worktree_path": worktree_path, "repo_path": repo_path},
    })
    return t


def test_reaps_terminal_worktree_past_ttl():
    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=72)
    tasks = [_task(TaskStatus.COMPLETED, old, "/repo/.worktrees/forge/a")]
    result = reapable_worktrees(tasks, now, timedelta(hours=48))
    assert result == [("/repo", "/repo/.worktrees/forge/a")]


def test_keeps_recent_terminal_worktree():
    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    recent = now - timedelta(hours=1)
    tasks = [_task(TaskStatus.COMPLETED, recent, "/repo/.worktrees/forge/a")]
    assert reapable_worktrees(tasks, now, timedelta(hours=48)) == []


def test_keeps_worktree_with_active_reference():
    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=72)
    tasks = [
        _task(TaskStatus.COMPLETED, old, "/repo/.worktrees/forge/a"),
        _task(TaskStatus.EXECUTING, old, "/repo/.worktrees/forge/a"),
    ]
    assert reapable_worktrees(tasks, now, timedelta(hours=48)) == []


def test_awaiting_approval_keeps_worktree():
    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=72)
    tasks = [_task(TaskStatus.AWAITING_APPROVAL, old, "/repo/.worktrees/forge/a")]
    assert reapable_worktrees(tasks, now, timedelta(hours=48)) == []


def test_shared_worktree_kept_alive_by_recent_followup():
    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=72)
    recent = now - timedelta(hours=2)
    wt = "/repo/.worktrees/forge/a"
    tasks = [
        _task(TaskStatus.COMPLETED, old, wt),     # parent, old
        _task(TaskStatus.COMPLETED, recent, wt),  # follow-up, recent
    ]
    assert reapable_worktrees(tasks, now, timedelta(hours=48)) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_worktree_reaper.py -v`
Expected: FAIL — `No module named 'forge.worktree_reaper'`.

- [ ] **Step 3: Write the pure decision function**

Create `forge/worktree_reaper.py`:

```python
"""Pure decision logic for reclaiming Code-task git worktrees.

Worktrees persist after delivery so follow-up tasks can `claude --continue` in
them. A worktree is reclaimable only when *every* task referencing it is terminal
and the most recently touched reference is older than the retention TTL. Grouping
by path keeps a shared worktree alive while any parent or recent follow-up still
references it.
"""

from datetime import datetime, timedelta

from forge.models import Task, TaskStatus

# A worktree referenced by any task in one of these states must not be reclaimed.
ACTIVE_STATES = {
    TaskStatus.QUEUED,
    TaskStatus.TRIAGING,
    TaskStatus.EXECUTING,
    TaskStatus.VERIFYING,
    TaskStatus.DELIVERING,
    TaskStatus.AWAITING_APPROVAL,
}


def reapable_worktrees(
    tasks: list[Task], now: datetime, ttl: timedelta
) -> list[tuple[str, str]]:
    """Return (repo_path, worktree_path) pairs whose worktree can be removed."""
    groups: dict[str, list[Task]] = {}
    for task in tasks:
        wt = (task.handler_data or {}).get("worktree_path")
        if wt:
            groups.setdefault(wt, []).append(task)

    reapable: list[tuple[str, str]] = []
    for worktree_path, group in groups.items():
        if any(t.status in ACTIVE_STATES for t in group):
            continue
        newest = max(t.updated_at for t in group)
        if now - newest <= ttl:
            continue
        repo_path = next(
            ((t.handler_data or {}).get("repo_path") for t in group if (t.handler_data or {}).get("repo_path")),
            None,
        )
        if repo_path:
            reapable.append((repo_path, worktree_path))
    return reapable
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_worktree_reaper.py -v`
Expected: PASS

- [ ] **Step 5: Add the store query**

In `forge/store.py`, add after `list_active_tasks` (near line 168):

```python
    async def list_tasks_with_worktrees(self) -> list[Task]:
        """Tasks whose handler_data carries a worktree_path — candidates for the
        worktree reaper. Low-volume single-box system, so a LIKE scan is fine."""
        rows = await self._db.fetch_all(
            "SELECT * FROM tasks WHERE handler_data LIKE '%\"worktree_path\"%'"
        )
        return [Task.from_row(row) for row in rows]
```

- [ ] **Step 6: Add the config setting**

In `forge/config.py`, add after `default_timeout_seconds` (line 18):

```python
    default_timeout_seconds: int = 1800
    worktree_ttl_hours: int = 48
```

- [ ] **Step 7: Write the coordinator integration test**

Append to `tests/test_coordinator_steering.py`:

```python
from datetime import datetime, timedelta, timezone


class _RecordingGit:
    def __init__(self):
        self.removed = []
        self.pruned = []

    async def cleanup_worktree(self, repo_path, worktree_path):
        self.removed.append((repo_path, worktree_path))

    async def prune_worktrees(self, repo_path):
        self.pruned.append(repo_path)


async def test_reap_old_worktrees_removes_stale(setup):
    store, coord = setup
    git = _RecordingGit()
    coord._git = git
    coord._worktree_ttl = timedelta(hours=48)

    old = datetime.now(timezone.utc) - timedelta(hours=72)
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d")
    task = task.model_copy(update={
        "status": TaskStatus.COMPLETED,
        "updated_at": old,
        "handler_data": {"worktree_path": "/repo/.worktrees/forge/a", "repo_path": "/repo"},
    })
    await store.save(task)
    # Backdate updated_at in the row (save uses the model's updated_at).
    await store._db.execute(
        "UPDATE tasks SET updated_at = ? WHERE id = ?", (old.isoformat(), task.id)
    )

    n = await coord.reap_old_worktrees()
    assert n == 1
    assert git.removed == [("/repo", "/repo/.worktrees/forge/a")]
    assert git.pruned == ["/repo"]


async def test_reap_old_worktrees_noop_without_git(setup):
    store, coord = setup
    coord._git = None
    assert await coord.reap_old_worktrees() == 0
```

- [ ] **Step 8: Run the coordinator test to verify it fails**

Run: `uv run pytest tests/test_coordinator_steering.py::test_reap_old_worktrees_removes_stale -v`
Expected: FAIL — `Coordinator` has no attribute `reap_old_worktrees` / `_git`.

- [ ] **Step 9: Add `git` + TTL to the coordinator and implement `reap_old_worktrees`**

In `forge/coordinator.py`, add the import near the top (with the other `from forge...` imports, e.g. after the `from forge.state import transition` line):

```python
from forge.worktree_reaper import reapable_worktrees
```

(`datetime`, `timedelta`, and `timezone` are already imported at the top of the file — line 4 — so no datetime import change is needed.)

Add a `git` parameter to `__init__` (after `watchers`, line 39) and store it + the TTL:

```python
        watchers: list | None = None,
        git=None,
    ):
        self._store = store
        self._registry = registry
        self._connectors = connectors
        self._settings = settings
        self._max_concurrent = max_concurrent
        self._poller = poller
        self._watchers = watchers or []
        self._git = git
        ttl_hours = getattr(settings, "worktree_ttl_hours", 48) if settings else 48
        self._worktree_ttl = timedelta(hours=ttl_hours)
```

Add the method (next to `reap_stuck_tasks`, after line 302):

```python
    async def reap_old_worktrees(self) -> int:
        """Reclaim Code-task git worktrees that are no longer referenced by any
        active task and whose newest reference is older than the TTL. No-ops when
        no git helper is wired (tests)."""
        if self._git is None:
            return 0
        tasks = await self._store.list_tasks_with_worktrees()
        targets = reapable_worktrees(
            tasks, datetime.now(timezone.utc), self._worktree_ttl
        )
        removed = 0
        for repo_path, worktree_path in targets:
            try:
                await self._git.cleanup_worktree(repo_path, worktree_path)
                await self._git.prune_worktrees(repo_path)
                removed += 1
            except Exception:
                logger.warning("Failed to reap worktree %s", worktree_path, exc_info=True)
        return removed
```

- [ ] **Step 10: Wire it into `tick`**

In `forge/coordinator.py`, after the `reap_stuck_tasks` block in `tick` (after line 124), add:

```python
        try:
            reaped_wt = await self.reap_old_worktrees()
            if reaped_wt > 0:
                logger.info("Reaped %d old worktrees", reaped_wt)
        except Exception:
            logger.exception("Error reaping old worktrees")
```

- [ ] **Step 11: Pass the git helper from main**

In `forge/main.py`, update the `Coordinator(...)` construction (lines 268-276) to pass a `GitOps`:

```python
        coordinator = Coordinator(
            store=store,
            registry=registry,
            connectors=connectors,
            settings=settings,
            max_concurrent=settings.max_concurrent_tasks,
            poller=poller,
            watchers=watchers,
            git=GitOps(settings.workspace_dir),
        )
```

(`GitOps` is already imported in `main.py` — confirm the import near the top; it is used at line 235.)

- [ ] **Step 12: Run the full reaper + coordinator suites**

Run: `uv run pytest tests/test_worktree_reaper.py tests/test_coordinator_steering.py tests/test_coordinator.py -v`
Expected: PASS

- [ ] **Step 13: Commit**

```bash
git add forge/worktree_reaper.py forge/store.py forge/coordinator.py forge/config.py forge/main.py tests/test_worktree_reaper.py tests/test_coordinator_steering.py
git commit -m "feat(coordinator): reference-aware worktree reaper on each tick"
```

---

### Task 7: Follow-up API endpoint

**Files:**
- Modify: `forge/api/tasks.py:1-8` (imports), add `POST /{task_id}/follow-up`
- Test: `tests/test_api_steering.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api_steering.py`. The existing `client` fixture yields the
tuple `(c, store, nudged)` — unpack it exactly like the other tests in this file:

```python
import os


async def test_follow_up_creates_linked_task(client, tmp_path):
    c, store, _ = client
    wt = tmp_path / "wt"
    wt.mkdir()
    parent = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="p", description="d", repo="o/r", require_approval=True)
    await store.save(parent)
    await store.update_status(parent.id, TaskStatus.COMPLETED)
    await store.update_handler_data(parent.id, {"worktree_path": str(wt)})

    resp = await c.post(f"/api/tasks/{parent.id}/follow-up", json={"prompt": "also add logging"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["continues_task_id"] == parent.id
    assert body["repo"] == "o/r"
    assert body["require_approval"] is True
    assert body["status"] == "queued"


async def test_follow_up_rejects_active_parent(client, tmp_path):
    c, store, _ = client
    wt = tmp_path / "wt2"
    wt.mkdir()
    parent = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="p", description="d", repo="o/r")
    await store.save(parent)
    await store.update_status(parent.id, TaskStatus.EXECUTING)
    await store.update_handler_data(parent.id, {"worktree_path": str(wt)})

    resp = await c.post(f"/api/tasks/{parent.id}/follow-up", json={"prompt": "x"})
    assert resp.status_code == 409


async def test_follow_up_rejects_reaped_worktree(client, tmp_path):
    c, store, _ = client
    parent = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="p", description="d", repo="o/r")
    await store.save(parent)
    await store.update_status(parent.id, TaskStatus.COMPLETED)
    await store.update_handler_data(parent.id, {"worktree_path": str(tmp_path / "gone")})

    resp = await c.post(f"/api/tasks/{parent.id}/follow-up", json={"prompt": "x"})
    assert resp.status_code == 409


async def test_follow_up_missing_parent_404(client):
    c, _, _ = client
    resp = await c.post("/api/tasks/does-not-exist/follow-up", json={"prompt": "x"})
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_steering.py::test_follow_up_creates_linked_task -v`
Expected: FAIL — 404/405 (route not defined).

- [ ] **Step 3: Implement the endpoint**

In `forge/api/tasks.py`, add `os` to the imports at the top (line 1 area):

```python
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
```

Add the validity-state set near `_TERMINAL` (after line 93):

```python
_FOLLOW_UP_OK = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.AWAITING_APPROVAL}
```

Add the request model near `CreateTaskRequest` (after line 43):

```python
class FollowUpRequest(BaseModel):
    prompt: str = Field(max_length=50_000)
```

Add the endpoint (after the `reject` endpoint at the end of the steering routes):

```python
@router.post("/{task_id}/follow-up")
async def follow_up_task(task_id: str, req: FollowUpRequest):
    """Queue a continuation of a finished Code task. The new task reuses the
    parent's worktree + Claude conversation (`claude --continue`)."""
    store = get_store()
    parent = await store.get(task_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if str(parent.type) != "code":
        raise HTTPException(status_code=409, detail="Only code tasks support follow-up")
    if parent.status not in _FOLLOW_UP_OK:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot follow up a {parent.status.value} task",
        )
    worktree_path = (parent.handler_data or {}).get("worktree_path")
    if not worktree_path or not os.path.isdir(worktree_path):
        raise HTTPException(
            status_code=409,
            detail="Parent worktree no longer available; it was reaped",
        )

    title = (req.prompt[:80] + "…") if len(req.prompt) > 80 else req.prompt
    follow_up = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.MANUAL,
        title=f"Follow-up: {title}",
        description=req.prompt,
        repo=parent.repo,
        require_approval=parent.require_approval,
        continues_task_id=parent.id,
    )
    await store.save(follow_up)

    if _coordinator is not None and hasattr(_coordinator, "nudge"):
        _coordinator.nudge()

    return _task_dict(follow_up)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api_steering.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add forge/api/tasks.py tests/test_api_steering.py
git commit -m "feat(api): POST /api/tasks/{id}/follow-up continuation endpoint"
```

---

### Task 8: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the whole backend suite**

Run: `uv run pytest -q`
Expected: PASS (all tests, including the ~378 prior + the new ones).

- [ ] **Step 2: App-boot smoke for the new route**

Run:

```bash
uv run python -c "
from forge.main import create_app
app = create_app()
paths = sorted(r.path for r in app.routes if 'tasks' in getattr(r, 'path', ''))
print([p for p in paths if 'follow-up' in p])
"
```

Expected: prints `['/api/tasks/{task_id}/follow-up']`.

- [ ] **Step 3: Commit (if any verification fixups were needed)**

```bash
git add -A
git commit -m "test: Phase 2b full-suite verification" || echo "nothing to commit"
```

---

## Notes for the implementer

- `create_app` is the app factory used in the smoke test; the existing Phase 2a smoke used the same shape.
- The Code agent's `execute` now builds the prompt once and appends retry context generically (instead of re-calling `build_prompt`). This is intentional and keeps the follow-up and fresh paths uniform; existing Code-agent tests only cover `triage`/`verify`, so they're unaffected.
- Do not re-introduce `cleanup_worktree` in `deliver` — the reaper is now the sole reclaim path (cancel/reject already only kill the session; their worktrees are reclaimed by the reaper too).
- `GitOps` is the concrete git helper class (not `GitHelper`); the Code agent stores it as `self._git`.
