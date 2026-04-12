# Research Handler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `ResearchHandler` that delegates open-ended web research to Claude Code and lands the output as a markdown file in the user's Obsidian Notebook.

**Architecture:** A new `forge/handlers/research.py` following the 4-stage handler shape. `execute()` runs `claude` CLI (via the existing `ClaudeRunner`) in the notebook working tree and diffs filesystem snapshots to detect new files. `verify()` enforces the Wiki/Fields/Log allowlist. `deliver()` summarizes the written files. Syncshot commits and pushes asynchronously (already shipped).

**Tech Stack:** Python 3.13, pytest + pytest-asyncio, `ClaudeRunner` (subprocess-based wrapper already in `forge/claude.py`).

**Spec:** `docs/superpowers/specs/2026-04-12-research-handler-design.md`

---

## File Structure

**Create:**
- `forge/handlers/research.py` — `ResearchHandler` class
- `forge/handlers/research_prompt.py` — `build_research_prompt` helper
- `tests/test_research_prompt.py`
- `tests/test_research_handler.py`

**Modify:**
- `forge/main.py` — register `ResearchHandler` when notebook is configured

---

## Task 1: Research prompt builder

**Files:**
- Create: `forge/handlers/research_prompt.py`
- Create: `tests/test_research_prompt.py`

- [ ] **Step 1: Write failing tests**

`tests/test_research_prompt.py`:
```python
from forge.handlers.research_prompt import build_research_prompt


def test_includes_title_and_description():
    prompt = build_research_prompt(
        title="OpenClaw Use Cases",
        description="Collect blog posts and YouTube summaries.",
    )
    assert "OpenClaw Use Cases" in prompt
    assert "Collect blog posts and YouTube summaries." in prompt


def test_mentions_vault_conventions():
    prompt = build_research_prompt(title="T", description="D")
    assert "CLAUDE.md" in prompt
    assert "Wiki/" in prompt
    assert "Fields/" in prompt


def test_forbids_disallowed_dirs():
    prompt = build_research_prompt(title="T", description="D")
    # At minimum People and +Templates are called out
    assert "People/" in prompt
    assert "+Templates/" in prompt


def test_retry_context_appended_when_provided():
    prompt = build_research_prompt(
        title="T",
        description="D",
        retry_context="Previous attempt timed out after 600s.",
    )
    assert "Previous Attempt" in prompt
    assert "Previous attempt timed out after 600s." in prompt


def test_retry_context_absent_when_none():
    prompt = build_research_prompt(title="T", description="D")
    assert "Previous Attempt" not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_research_prompt.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `build_research_prompt`**

`forge/handlers/research_prompt.py`:
```python
"""Prompt builder for the research task handler."""


def build_research_prompt(
    title: str,
    description: str,
    retry_context: str | None = None,
) -> str:
    parts = [
        f"# Research Task: {title}",
        f"\n## Description\n{description}",
        "\n## Instructions",
        "- You are working inside an Obsidian vault (the user's personal notebook).",
        "- Read ./CLAUDE.md first for the vault's conventions on Wiki vs Fields vs Log.",
        "- Use WebSearch and WebFetch to gather information from authoritative sources.",
        "- Synthesize findings into a single markdown file.",
        "- Decide the best path: Wiki/ for transferable knowledge, Fields/ for ongoing life areas.",
        "  Never write to People/, Projects/, +Templates/, +Assets/, or any .base file.",
        "- Use [[Wikilinks]] when referencing concepts or people that may already exist in the vault.",
        "- Include specific references (URLs, titles, authors) so the user can dig deeper.",
        "- Do not commit; just write the file.",
    ]
    if retry_context:
        parts.append(f"\n## Previous Attempt\n{retry_context}")
    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_research_prompt.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add forge/handlers/research_prompt.py tests/test_research_prompt.py
git commit -m "feat(research): add research task prompt builder"
```

---

## Task 2: Handler scaffold + triage

**Files:**
- Create: `forge/handlers/research.py`
- Create: `tests/test_research_handler.py`

- [ ] **Step 1: Write failing tests**

`tests/test_research_handler.py`:
```python
from pathlib import Path

import pytest

from forge.handlers.research import ResearchHandler
from forge.models import Task, TaskSource, TaskType


class StubClaudeRunner:
    """Minimal stand-in for ClaudeRunner used by handler tests."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.side_effect = None  # Callable[[prompt, work_dir], str] or Exception class iter

    async def run(self, prompt: str, work_dir: str) -> str:
        self.calls.append((prompt, work_dir))
        if self.side_effect is not None:
            result = self.side_effect(prompt, work_dir)
            if isinstance(result, Exception):
                raise result
            return result
        return ""


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    for d in ("Wiki", "Fields", "Log", "People", "+Templates"):
        (tmp_path / d).mkdir()
    (tmp_path / "CLAUDE.md").write_text("# Notebook conventions")
    return tmp_path


@pytest.fixture
def runner() -> StubClaudeRunner:
    return StubClaudeRunner()


@pytest.fixture
def handler(vault: Path, runner: StubClaudeRunner) -> ResearchHandler:
    return ResearchHandler(claude_runner=runner, notebook_root=vault)


def _research_task(title: str = "OpenClaw Use Cases", description: str = "Collect blog posts.") -> Task:
    return Task.new(
        task_type=TaskType.RESEARCH,
        source=TaskSource.CHAT,
        title=title,
        description=description,
    )


def test_handler_task_type(handler: ResearchHandler):
    assert handler.task_type == "research"


@pytest.mark.asyncio
async def test_triage_accepts_non_empty_title(handler: ResearchHandler):
    task = _research_task(title="Real title")
    assert await handler.triage(task) is True


@pytest.mark.asyncio
async def test_triage_declines_empty_title(handler: ResearchHandler):
    task = _research_task(title="")
    assert await handler.triage(task) is False


@pytest.mark.asyncio
async def test_triage_declines_whitespace_title(handler: ResearchHandler):
    task = _research_task(title="   ")
    assert await handler.triage(task) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_research_handler.py -v`
Expected: FAIL — `ResearchHandler` doesn't exist.

- [ ] **Step 3: Implement scaffold and triage**

`forge/handlers/research.py`:
```python
"""Research task handler — runs Claude Code in the Notebook vault."""

import logging
from pathlib import Path

from forge.claude import ClaudeRunner
from forge.models import Task

logger = logging.getLogger(__name__)

ALLOWED_WRITE_PREFIXES = ("Wiki/", "Fields/", "Log/")
MAX_RETRIES = 2
MIN_FILE_BYTES = 200


class ResearchHandler:
    task_type: str = "research"

    def __init__(
        self,
        claude_runner: ClaudeRunner,
        notebook_root: Path,
    ):
        self._claude = claude_runner
        self._root = notebook_root

    async def triage(self, task: Task) -> bool:
        if not task.title or not task.title.strip():
            logger.warning(f"Task {task.id} has empty title, declining")
            return False
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_research_handler.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add forge/handlers/research.py tests/test_research_handler.py
git commit -m "feat(research): add ResearchHandler scaffold with triage"
```

---

## Task 3: `execute` with snapshot diff

**Files:**
- Modify: `forge/handlers/research.py`
- Modify: `tests/test_research_handler.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_research_handler.py`:
```python
@pytest.mark.asyncio
async def test_execute_detects_new_file(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    def write_file(_prompt: str, _work_dir: str) -> str:
        (vault / "Wiki" / "OpenClaw.md").write_text("# OpenClaw\n\n" + "x" * 300)
        return "done"

    runner.side_effect = write_file
    task = _research_task()
    result = await handler.execute(task)

    assert result["new_files"] == ["Wiki/OpenClaw.md"]
    assert result["claude_output"] == "done"


@pytest.mark.asyncio
async def test_execute_ignores_pre_existing_files(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    (vault / "Wiki" / "Existing.md").write_text("pre-existing content")

    def write_file(_prompt: str, _work_dir: str) -> str:
        (vault / "Wiki" / "New.md").write_text("new content" * 50)
        return ""

    runner.side_effect = write_file
    task = _research_task()
    result = await handler.execute(task)

    assert result["new_files"] == ["Wiki/New.md"]


@pytest.mark.asyncio
async def test_execute_passes_notebook_root_as_work_dir(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    task = _research_task()
    await handler.execute(task)
    assert len(runner.calls) == 1
    _prompt, work_dir = runner.calls[0]
    assert work_dir == str(vault)


@pytest.mark.asyncio
async def test_execute_ignores_files_outside_allowed_prefixes(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    def write_elsewhere(_prompt: str, _work_dir: str) -> str:
        (vault / "People" / "Foo.md").write_text("oops")
        return ""

    runner.side_effect = write_elsewhere
    task = _research_task()
    result = await handler.execute(task)
    # Snapshot is limited to allowed prefixes — a write to People/ is invisible
    assert result["new_files"] == []


@pytest.mark.asyncio
async def test_execute_truncates_claude_output(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    def huge_output(_prompt: str, _work_dir: str) -> str:
        return "x" * 5000

    runner.side_effect = huge_output
    task = _research_task()
    result = await handler.execute(task)
    assert len(result["claude_output"]) == 2000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_research_handler.py -v -k execute`
Expected: FAIL — `execute` not implemented.

- [ ] **Step 3: Implement `execute`**

Append to `ResearchHandler`:
```python
    def _snapshot(self) -> set[str]:
        """Relative paths of all files under allowed prefixes."""
        found: set[str] = set()
        for prefix in ALLOWED_WRITE_PREFIXES:
            base = self._root / prefix.rstrip("/")
            if not base.is_dir():
                continue
            for path in base.rglob("*"):
                if path.is_file():
                    found.add(str(path.relative_to(self._root)))
        return found

    async def execute(self, task: Task) -> dict:
        from forge.handlers.research_prompt import build_research_prompt

        before = self._snapshot()
        prompt = build_research_prompt(title=task.title, description=task.description)
        output = await self._claude.run(prompt, str(self._root))
        after = self._snapshot()
        new_files = sorted(after - before)
        return {
            "claude_output": output[:2000],
            "new_files": new_files,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_research_handler.py -v`
Expected: all passed (9 tests total).

- [ ] **Step 5: Commit**

```bash
git add forge/handlers/research.py tests/test_research_handler.py
git commit -m "feat(research): implement execute with snapshot diff"
```

---

## Task 4: `execute` retry logic

**Files:**
- Modify: `forge/handlers/research.py`
- Modify: `tests/test_research_handler.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_research_handler.py`:
```python
@pytest.mark.asyncio
async def test_execute_retries_on_timeout(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    call_count = {"n": 0}

    def flaky(_prompt: str, _work_dir: str) -> str:
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise TimeoutError("first try")
        (vault / "Wiki" / "Later.md").write_text("x" * 300)
        return "ok"

    runner.side_effect = flaky
    task = _research_task()
    result = await handler.execute(task)
    assert call_count["n"] == 2
    assert result["new_files"] == ["Wiki/Later.md"]


@pytest.mark.asyncio
async def test_execute_retries_on_runtime_error(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    call_count = {"n": 0}

    def flaky(_prompt: str, _work_dir: str) -> str:
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise RuntimeError("boom")
        (vault / "Wiki" / "Finally.md").write_text("x" * 300)
        return "ok"

    runner.side_effect = flaky
    task = _research_task()
    result = await handler.execute(task)
    assert call_count["n"] == 3
    assert result["new_files"] == ["Wiki/Finally.md"]


@pytest.mark.asyncio
async def test_execute_raises_after_max_retries(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    def always_fail(_prompt: str, _work_dir: str) -> str:
        raise TimeoutError("forever")

    runner.side_effect = always_fail
    task = _research_task()
    with pytest.raises(TimeoutError):
        await handler.execute(task)


@pytest.mark.asyncio
async def test_execute_retry_passes_context_to_prompt(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    prompts: list[str] = []
    call_count = {"n": 0}

    def capture(prompt: str, _work_dir: str) -> str:
        prompts.append(prompt)
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise RuntimeError("first failure message")
        (vault / "Wiki" / "Ok.md").write_text("x" * 300)
        return "ok"

    runner.side_effect = capture
    task = _research_task()
    await handler.execute(task)
    assert "Previous Attempt" in prompts[1]
    assert "first failure message" in prompts[1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_research_handler.py -v -k retry`
Expected: FAIL — retry logic not implemented.

- [ ] **Step 3: Implement retry in `execute`**

Replace the `execute` method:
```python
    async def execute(self, task: Task) -> dict:
        from forge.handlers.research_prompt import build_research_prompt

        before = self._snapshot()
        retry_context: str | None = None
        output = ""

        for attempt in range(MAX_RETRIES + 1):
            prompt = build_research_prompt(
                title=task.title,
                description=task.description,
                retry_context=retry_context,
            )
            try:
                output = await self._claude.run(prompt, str(self._root))
                break
            except (TimeoutError, RuntimeError) as e:
                logger.warning(f"Research attempt {attempt + 1} failed: {e}")
                retry_context = f"Attempt {attempt + 1} failed: {e}"
                if attempt == MAX_RETRIES:
                    raise

        after = self._snapshot()
        new_files = sorted(after - before)
        return {
            "claude_output": output[:2000],
            "new_files": new_files,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_research_handler.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add forge/handlers/research.py tests/test_research_handler.py
git commit -m "feat(research): retry execute on timeout/runtime errors"
```

---

## Task 5: `verify` with allowlist + stub guard

**Files:**
- Modify: `forge/handlers/research.py`
- Modify: `tests/test_research_handler.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_research_handler.py`:
```python
@pytest.mark.asyncio
async def test_verify_true_when_new_file_in_allowed_dir_with_content(handler: ResearchHandler, vault: Path):
    (vault / "Wiki" / "Ok.md").write_text("x" * 300)
    task = _research_task()
    task.handler_data = {"new_files": ["Wiki/Ok.md"]}
    assert await handler.verify(task) is True


@pytest.mark.asyncio
async def test_verify_false_when_no_new_files(handler: ResearchHandler):
    task = _research_task()
    task.handler_data = {"new_files": []}
    assert await handler.verify(task) is False


@pytest.mark.asyncio
async def test_verify_false_when_file_too_small(handler: ResearchHandler, vault: Path):
    (vault / "Wiki" / "Stub.md").write_text("tiny")
    task = _research_task()
    task.handler_data = {"new_files": ["Wiki/Stub.md"]}
    assert await handler.verify(task) is False


@pytest.mark.asyncio
async def test_verify_false_when_only_file_is_outside_allowlist(handler: ResearchHandler, vault: Path):
    (vault / "People" / "Foo.md").write_text("x" * 300)
    task = _research_task()
    task.handler_data = {"new_files": ["People/Foo.md"]}
    assert await handler.verify(task) is False


@pytest.mark.asyncio
async def test_verify_true_when_mixed_files_include_valid_one(handler: ResearchHandler, vault: Path):
    (vault / "People" / "Foo.md").write_text("x" * 300)
    (vault / "Fields").mkdir(exist_ok=True)
    (vault / "Fields" / "Redpanda.md").write_text("x" * 300)
    task = _research_task()
    task.handler_data = {"new_files": ["People/Foo.md", "Fields/Redpanda.md"]}
    assert await handler.verify(task) is True


@pytest.mark.asyncio
async def test_verify_false_when_file_missing_from_disk(handler: ResearchHandler):
    task = _research_task()
    task.handler_data = {"new_files": ["Wiki/Vanished.md"]}
    assert await handler.verify(task) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_research_handler.py -v -k verify`
Expected: FAIL — `verify` not implemented.

- [ ] **Step 3: Implement `verify`**

Append to `ResearchHandler`:
```python
    async def verify(self, task: Task) -> bool:
        new_files = task.handler_data.get("new_files", [])
        for rel in new_files:
            if not any(rel.startswith(prefix) for prefix in ALLOWED_WRITE_PREFIXES):
                continue
            path = self._root / rel
            if not path.is_file():
                continue
            if path.stat().st_size < MIN_FILE_BYTES:
                continue
            return True
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_research_handler.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add forge/handlers/research.py tests/test_research_handler.py
git commit -m "feat(research): implement verify with allowlist + stub guard"
```

---

## Task 6: `deliver` with per-file summaries

**Files:**
- Modify: `forge/handlers/research.py`
- Modify: `tests/test_research_handler.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_research_handler.py`:
```python
@pytest.mark.asyncio
async def test_deliver_returns_summaries(handler: ResearchHandler, vault: Path):
    content = "# OpenClaw\n\nAn agentic platform built on Claude.\n" + ("word " * 50)
    (vault / "Wiki" / "OpenClaw.md").write_text(content)

    task = _research_task()
    task.handler_data = {"new_files": ["Wiki/OpenClaw.md"]}

    result = await handler.deliver(task)
    assert result["status"] == "delivered"
    assert result["notebook_commit_pending"] is True
    assert len(result["files"]) == 1
    summary = result["files"][0]
    assert summary["path"] == "Wiki/OpenClaw.md"
    assert summary["word_count"] >= 50
    assert summary["preview"].startswith("# OpenClaw")


@pytest.mark.asyncio
async def test_deliver_truncates_preview(handler: ResearchHandler, vault: Path):
    long = "a" * 2000
    (vault / "Wiki" / "Long.md").write_text(long)
    task = _research_task()
    task.handler_data = {"new_files": ["Wiki/Long.md"]}
    result = await handler.deliver(task)
    assert len(result["files"][0]["preview"]) == 500


@pytest.mark.asyncio
async def test_deliver_skips_files_outside_allowlist(handler: ResearchHandler, vault: Path):
    (vault / "Wiki" / "Keep.md").write_text("x" * 300)
    (vault / "People" / "Skip.md").write_text("x" * 300)
    task = _research_task()
    task.handler_data = {"new_files": ["Wiki/Keep.md", "People/Skip.md"]}
    result = await handler.deliver(task)
    paths = [f["path"] for f in result["files"]]
    assert paths == ["Wiki/Keep.md"]


@pytest.mark.asyncio
async def test_deliver_skips_missing_files(handler: ResearchHandler, vault: Path):
    (vault / "Wiki" / "Real.md").write_text("x" * 300)
    task = _research_task()
    task.handler_data = {"new_files": ["Wiki/Real.md", "Wiki/Gone.md"]}
    result = await handler.deliver(task)
    paths = [f["path"] for f in result["files"]]
    assert paths == ["Wiki/Real.md"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_research_handler.py -v -k deliver`
Expected: FAIL — `deliver` not implemented.

- [ ] **Step 3: Implement `deliver`**

Append to `ResearchHandler`:
```python
    async def deliver(self, task: Task) -> dict:
        new_files = task.handler_data.get("new_files", [])
        summaries: list[dict] = []
        for rel in new_files:
            if not any(rel.startswith(prefix) for prefix in ALLOWED_WRITE_PREFIXES):
                continue
            path = self._root / rel
            if not path.is_file():
                continue
            text = path.read_text()
            summaries.append(
                {
                    "path": rel,
                    "word_count": len(text.split()),
                    "preview": text[:500],
                }
            )
        return {
            "status": "delivered",
            "files": summaries,
            "notebook_commit_pending": True,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_research_handler.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add forge/handlers/research.py tests/test_research_handler.py
git commit -m "feat(research): implement deliver with per-file summaries"
```

---

## Task 7: Register handler in `forge/main.py`

**Files:**
- Modify: `forge/main.py`

- [ ] **Step 1: Register handler when notebook is available**

In `forge/main.py`, locate the block (inside `lifespan`, inside `run()`) where `NotebookReader`/`NotebookWriter` are constructed (added in the notebook integration plan). After that block and after `registry.register(CodeHandler(...))`, add:

```python
        if notebook_reader is not None:
            from forge.claude import ClaudeRunner
            from forge.handlers.research import ResearchHandler

            registry.register(
                ResearchHandler(
                    claude_runner=ClaudeRunner(
                        model=settings.anthropic_api_key and "claude-sonnet-4-20250514" or "claude-sonnet-4-20250514",
                        timeout=600,
                    ),
                    notebook_root=Path(settings.notebook_dir),
                )
            )
```

Note: the `Path` import is already present from the notebook-reader construction block above. If not, add `from pathlib import Path` at the top of the function.

Simpler version (drop the ternary, just pass the model directly):

```python
        if notebook_reader is not None:
            from forge.claude import ClaudeRunner
            from forge.handlers.research import ResearchHandler

            registry.register(
                ResearchHandler(
                    claude_runner=ClaudeRunner(
                        model="claude-sonnet-4-20250514",
                        timeout=600,
                    ),
                    notebook_root=Path(settings.notebook_dir),
                )
            )
```

Use the simpler version.

- [ ] **Step 2: Verify app still starts and test suite is green**

Run: `uv run python -c "from forge.main import create_app; app = create_app(); print('ok')"`
Expected: `ok`

Run: `uv run pytest -x`
Expected: all tests pass (no regressions).

- [ ] **Step 3: Commit**

```bash
git add forge/main.py
git commit -m "feat(research): register ResearchHandler when notebook configured"
```

---

## Task 8: Deploy and verify end-to-end

**Files:** (none — verification only)

- [ ] **Step 1: Push to trigger autodeploy**

```bash
git push
ssh -t thomaseckert@ardent-forge.feist-gondola.ts.net "sudo systemctl start ardent-forge-autodeploy"
```

Wait for NTFY success notification (or accept that unrelated failing services like `ollama-model-pull` may still cause autodeploy to report FAILED — check `systemctl status ardent-forge` to confirm the main service activated).

- [ ] **Step 2: Confirm service is running new code**

```bash
ssh thomaseckert@ardent-forge.feist-gondola.ts.net "systemctl is-active ardent-forge && curl -s http://127.0.0.1:7030/health"
```

Expected: `active`, plus a JSON health response.

- [ ] **Step 3: Create a small research task via the UI**

In the Ardent Forge web UI (https://<tailnet-domain>), create a new task:
- Type: research
- Title: "Autodeploy Test Research"
- Description: "Summarize in 2-3 paragraphs what the Nix flake system does. Write the result to Wiki/."

Submit the task.

- [ ] **Step 4: Monitor**

```bash
ssh thomaseckert@ardent-forge.feist-gondola.ts.net "journalctl -u ardent-forge -f"
```

Watch for the handler to triage → execute → verify → deliver. Should complete within a few minutes.

- [ ] **Step 5: Verify output**

Check the task detail in the UI. Confirm the `files` summary includes `path`, `word_count`, `preview`.

On the box:
```bash
ssh thomaseckert@ardent-forge.feist-gondola.ts.net "ls -la /data/ardent-forge/notebook/Wiki/ | head"
```

Expected: a new `.md` file related to the task.

Wait ~45s, then on your laptop:
```bash
cd ~/.claude-worktrees/Notebook/hopeful-greider
git fetch origin main
git log origin/main -1 --name-only
```

Expected: the new file is in the most recent commit authored by "Ardent Forge".

Clean up if you like:
```bash
ssh thomaseckert@ardent-forge.feist-gondola.ts.net "cd /data/ardent-forge/notebook && rm Wiki/Autodeploy*.md"
```

- [ ] **Step 6: No commit** — this task is verification only.

---

## Self-review

**Spec coverage:**
- `triage` returns True on non-empty title, declines otherwise → Task 2
- `execute` snapshots before/after, runs Claude in notebook root → Task 3
- Retry on timeout/runtime error, up to 2 times → Task 4
- `verify` requires ≥1 new file under allowed prefix, ≥ 200 bytes → Task 5
- `deliver` returns per-file summaries with path/word_count/preview → Task 6
- `notebook_commit_pending: true` in deliver result → Task 6
- Prompt structure with vault conventions + forbidden dirs + retry context → Task 1
- Handler registered only when notebook is available → Task 7
- No git operations in handler (syncshot handles push) → design enforced by absence of git calls in every task
- End-to-end verification on the box → Task 8

All spec requirements covered.

**Placeholder scan:** no TBD/TODO/"handle edge cases" — every step has concrete code.

**Type consistency:** `ResearchHandler`, `build_research_prompt`, `ALLOWED_WRITE_PREFIXES`, `MAX_RETRIES`, `MIN_FILE_BYTES`, `StubClaudeRunner` defined once and referenced consistently. `handler_data["new_files"]` used identically by execute (writes), verify (reads), deliver (reads). Import of `build_research_prompt` is local to `execute` to avoid circular-import risk (handlers package stays light at import time).

---
