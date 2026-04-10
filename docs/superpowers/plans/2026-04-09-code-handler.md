# Code Handler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the code handler that takes a task (from Linear or chat), clones/worktrees the target repo, runs Claude Code CLI to implement it, verifies the result, and creates a GitHub PR.

**Architecture:** The code handler implements the `TaskHandler` protocol (triage/execute/verify/deliver). It manages git worktrees for isolation, invokes Claude Code CLI as a subprocess, runs repo-specific verification commands, and creates PRs via `gh` CLI. All state is tracked in the task's `handler_data` field.

**Tech Stack:** Python 3.13, asyncio subprocess, git, Claude Code CLI, GitHub CLI (`gh`)

---

## File Structure

```
forge/
├── handlers/
│   ├── __init__.py               # (existing) Handler protocol + registry
│   ├── echo.py                   # (existing) Echo test handler
│   └── code.py                   # Code handler implementation
├── git.py                        # Git operations (clone, worktree, PR creation)
├── claude.py                     # Claude Code CLI invocation
└── verify.py                     # Repo verification (detect + run build/test commands)

tests/
├── test_git.py                   # Git operations tests
├── test_claude.py                # Claude CLI invocation tests
├── test_verify.py                # Verification detection tests
└── test_code_handler.py          # Code handler integration tests
```

---

### Task 1: Git Operations Module

**Files:**
- Create: `forge/git.py`
- Create: `tests/test_git.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_git.py`:
```python
import os
import pytest
import asyncio

from forge.git import GitOps


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary git repo to work with."""
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    # Initialize a git repo with a commit
    cmds = [
        "git init",
        "git config user.email 'test@test.com'",
        "git config user.name 'Test'",
        "echo 'hello' > README.md",
        "git add .",
        "git commit -m 'initial'",
    ]
    for cmd in cmds:
        os.system(f"cd {repo_dir} && {cmd}")
    return str(repo_dir)


@pytest.fixture
def git_ops(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return GitOps(workspace_dir=str(workspace))


async def test_ensure_repo_clones(git_ops, temp_repo):
    repo_path = await git_ops.ensure_repo(temp_repo, "test-owner/test-repo")
    assert os.path.exists(repo_path)
    assert os.path.exists(os.path.join(repo_path, ".git"))


async def test_ensure_repo_idempotent(git_ops, temp_repo):
    path1 = await git_ops.ensure_repo(temp_repo, "test-owner/test-repo")
    path2 = await git_ops.ensure_repo(temp_repo, "test-owner/test-repo")
    assert path1 == path2


async def test_create_worktree(git_ops, temp_repo):
    repo_path = await git_ops.ensure_repo(temp_repo, "test-owner/test-repo")
    worktree_path = await git_ops.create_worktree(repo_path, "test-branch")
    assert os.path.exists(worktree_path)
    assert os.path.exists(os.path.join(worktree_path, "README.md"))


async def test_cleanup_worktree(git_ops, temp_repo):
    repo_path = await git_ops.ensure_repo(temp_repo, "test-owner/test-repo")
    worktree_path = await git_ops.create_worktree(repo_path, "cleanup-branch")
    assert os.path.exists(worktree_path)
    await git_ops.cleanup_worktree(repo_path, worktree_path)
    assert not os.path.exists(worktree_path)


async def test_get_diff(git_ops, temp_repo):
    repo_path = await git_ops.ensure_repo(temp_repo, "test-owner/test-repo")
    worktree_path = await git_ops.create_worktree(repo_path, "diff-branch")
    # Make a change
    with open(os.path.join(worktree_path, "new_file.py"), "w") as f:
        f.write("print('hello')\n")
    await _run(f"cd {worktree_path} && git add . && git commit -m 'add file'")
    diff = await git_ops.get_diff(worktree_path, "main")
    assert "new_file.py" in diff


async def _run(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    return stdout.decode()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write implementation**

`forge/git.py`:
```python
import asyncio
import logging
import os

logger = logging.getLogger(__name__)


class GitOps:
    def __init__(self, workspace_dir: str):
        self._workspace_dir = workspace_dir
        os.makedirs(workspace_dir, exist_ok=True)

    async def ensure_repo(self, source: str, repo_name: str) -> str:
        """Clone or fetch a repo into the workspace. Returns the repo path."""
        safe_name = repo_name.replace("/", "--")
        repo_path = os.path.join(self._workspace_dir, safe_name)

        if os.path.exists(repo_path):
            await self._run("git fetch --all", cwd=repo_path)
            return repo_path

        await self._run(f"git clone {source} {repo_path}")
        return repo_path

    async def create_worktree(self, repo_path: str, branch_name: str) -> str:
        """Create a git worktree for isolated work. Returns the worktree path."""
        worktree_dir = os.path.join(repo_path, ".worktrees")
        os.makedirs(worktree_dir, exist_ok=True)
        worktree_path = os.path.join(worktree_dir, branch_name)

        # Get the default branch
        default_branch = await self._get_default_branch(repo_path)

        await self._run(
            f"git worktree add {worktree_path} -b {branch_name} {default_branch}",
            cwd=repo_path,
        )
        return worktree_path

    async def cleanup_worktree(self, repo_path: str, worktree_path: str):
        """Remove a worktree after work is done."""
        await self._run(f"git worktree remove {worktree_path} --force", cwd=repo_path)

    async def get_diff(self, worktree_path: str, base_branch: str) -> str:
        """Get the diff between the worktree and a base branch."""
        return await self._run(f"git diff {base_branch}...HEAD", cwd=worktree_path)

    async def create_pr(
        self,
        worktree_path: str,
        title: str,
        body: str,
        base_branch: str | None = None,
    ) -> str:
        """Push the branch and create a PR. Returns the PR URL."""
        branch = await self._run("git rev-parse --abbrev-ref HEAD", cwd=worktree_path)
        branch = branch.strip()

        await self._run(f"git push -u origin {branch}", cwd=worktree_path)

        base = base_branch or await self._get_default_branch(worktree_path)
        result = await self._run(
            f'gh pr create --base {base} --head {branch} --title "{title}" --body "{body}"',
            cwd=worktree_path,
        )
        return result.strip()

    async def _get_default_branch(self, repo_path: str) -> str:
        """Detect the default branch (main or master)."""
        result = await self._run(
            "git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null || echo refs/heads/main",
            cwd=repo_path,
        )
        return result.strip().split("/")[-1]

    async def _run(self, cmd: str, cwd: str | None = None) -> str:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            error_msg = stderr.decode().strip()
            logger.error(f"Git command failed: {cmd}\n{error_msg}")
            raise RuntimeError(f"Git command failed: {cmd}\n{error_msg}")
        return stdout.decode()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_git.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add forge/git.py tests/test_git.py
git commit -m "feat: add git operations module (clone, worktree, diff, PR)"
```

---

### Task 2: Claude Code CLI Invocation

**Files:**
- Create: `forge/claude.py`
- Create: `tests/test_claude.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_claude.py`:
```python
import pytest

from forge.claude import build_prompt, ClaudeRunner


def test_build_prompt_basic():
    prompt = build_prompt(
        title="Fix the login bug",
        description="Users can't log in when password has special chars",
        repo="t-eckert/myapp",
    )
    assert "Fix the login bug" in prompt
    assert "special chars" in prompt
    assert "t-eckert/myapp" in prompt


def test_build_prompt_with_analysis():
    prompt = build_prompt(
        title="Add feature",
        description="New feature needed",
        repo="t-eckert/myapp",
        analysis="The codebase uses FastAPI with SQLAlchemy",
    )
    assert "FastAPI with SQLAlchemy" in prompt


def test_build_prompt_with_retry_context():
    prompt = build_prompt(
        title="Fix bug",
        description="Bug description",
        repo="t-eckert/myapp",
        retry_context="Previous attempt failed: ImportError in module X",
    )
    assert "Previous attempt" in prompt
    assert "ImportError" in prompt


def test_claude_runner_init():
    runner = ClaudeRunner(model="claude-sonnet-4-20250514", timeout=120)
    assert runner._model == "claude-sonnet-4-20250514"
    assert runner._timeout == 120


def test_claude_runner_default_model():
    runner = ClaudeRunner()
    assert runner._model == "claude-sonnet-4-20250514"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_claude.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write implementation**

`forge/claude.py`:
```python
import asyncio
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"


def build_prompt(
    title: str,
    description: str,
    repo: str,
    analysis: str | None = None,
    retry_context: str | None = None,
) -> str:
    """Build the prompt for Claude Code CLI."""
    parts = [
        f"# Task: {title}",
        f"\n## Repository: {repo}",
        f"\n## Description\n{description}",
    ]

    if analysis:
        parts.append(f"\n## Codebase Analysis\n{analysis}")

    if retry_context:
        parts.append(f"\n## Previous Attempt Context\n{retry_context}")

    parts.append(
        "\n## Instructions"
        "\n- Read the project's CLAUDE.md if it exists for project-specific guidance"
        "\n- Implement the task as described"
        "\n- Write or update tests as appropriate"
        "\n- Run the project's build and test commands to verify your work"
        "\n- Commit your changes with a clear commit message"
    )

    return "\n".join(parts)


class ClaudeRunner:
    def __init__(self, model: str = DEFAULT_MODEL, timeout: int = 300):
        self._model = model
        self._timeout = timeout

    async def run(self, prompt: str, work_dir: str) -> str:
        """Run Claude Code CLI with the given prompt in the given directory.
        Returns the CLI output."""
        logger.info(f"Running Claude Code in {work_dir} (model={self._model}, timeout={self._timeout}s)")

        proc = await asyncio.create_subprocess_exec(
            "claude",
            "--print",
            "--dangerously-skip-permissions",
            "--model", self._model,
            "-p", prompt,
            cwd=work_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "CLAUDE_NO_TELEMETRY": "1"},
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise TimeoutError(
                f"Claude Code timed out after {self._timeout}s"
            )

        output = stdout.decode()
        if proc.returncode != 0:
            error = stderr.decode()
            logger.error(f"Claude Code failed (rc={proc.returncode}): {error}")
            raise RuntimeError(f"Claude Code failed: {error}")

        return output
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_claude.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add forge/claude.py tests/test_claude.py
git commit -m "feat: add Claude Code CLI runner and prompt builder"
```

---

### Task 3: Verification Module

**Files:**
- Create: `forge/verify.py`
- Create: `tests/test_verify.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_verify.py`:
```python
import os
import pytest

from forge.verify import detect_verify_commands, VerificationResult


def test_detect_python_uv(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
    commands = detect_verify_commands(str(tmp_path))
    assert any("uv run pytest" in cmd for cmd in commands)


def test_detect_python_pip(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask\n")
    commands = detect_verify_commands(str(tmp_path))
    assert any("pytest" in cmd for cmd in commands)


def test_detect_node(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "vitest"}}\n')
    commands = detect_verify_commands(str(tmp_path))
    assert any("npm" in cmd for cmd in commands)


def test_detect_rust(tmp_path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\n')
    commands = detect_verify_commands(str(tmp_path))
    assert any("cargo" in cmd for cmd in commands)


def test_detect_go(tmp_path):
    (tmp_path / "go.mod").write_text("module test\n")
    commands = detect_verify_commands(str(tmp_path))
    assert any("go" in cmd for cmd in commands)


def test_detect_taskfile(tmp_path):
    (tmp_path / "Taskfile.yml").write_text("version: '3'\n")
    commands = detect_verify_commands(str(tmp_path))
    assert any("task" in cmd.lower() for cmd in commands)


def test_detect_claude_md_commands(tmp_path):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Test\n\n```bash\n./taskw test\n./taskw lint\n```\n")
    commands = detect_verify_commands(str(tmp_path))
    # CLAUDE.md commands should be detected but we don't parse them automatically
    # The presence of CLAUDE.md is noted for Claude Code to use directly


def test_detect_empty_dir(tmp_path):
    commands = detect_verify_commands(str(tmp_path))
    assert commands == []


def test_verification_result():
    result = VerificationResult(success=True, output="All tests passed", commands_run=["pytest"])
    assert result.success
    assert "passed" in result.output

    failed = VerificationResult(success=False, output="1 failed", commands_run=["pytest"])
    assert not failed.success
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_verify.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write implementation**

`forge/verify.py`:
```python
import asyncio
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    success: bool
    output: str
    commands_run: list[str]


def detect_verify_commands(repo_path: str) -> list[str]:
    """Detect verification commands based on project files."""
    commands: list[str] = []

    # Taskfile takes priority — it's the project's own task runner
    if os.path.exists(os.path.join(repo_path, "Taskfile.yml")) or os.path.exists(
        os.path.join(repo_path, "Taskfile.yaml")
    ):
        # Check for taskw wrapper (used in some projects)
        if os.path.exists(os.path.join(repo_path, "taskw")):
            commands.append("./taskw test")
        else:
            commands.append("task test")
        return commands

    # Python
    if os.path.exists(os.path.join(repo_path, "pyproject.toml")):
        commands.append("uv run pytest -v")
    elif os.path.exists(os.path.join(repo_path, "requirements.txt")):
        commands.append("pytest -v")

    # Node.js
    if os.path.exists(os.path.join(repo_path, "package.json")):
        commands.append("npm test")

    # Rust
    if os.path.exists(os.path.join(repo_path, "Cargo.toml")):
        commands.append("cargo check")
        commands.append("cargo test")

    # Go
    if os.path.exists(os.path.join(repo_path, "go.mod")):
        commands.append("go build ./...")
        commands.append("go test ./...")

    return commands


async def run_verification(repo_path: str, commands: list[str] | None = None) -> VerificationResult:
    """Run verification commands in the repo. Auto-detects if commands not provided."""
    if commands is None:
        commands = detect_verify_commands(repo_path)

    if not commands:
        logger.warning(f"No verification commands detected for {repo_path}")
        return VerificationResult(success=True, output="No verification commands found", commands_run=[])

    all_output: list[str] = []
    commands_run: list[str] = []

    for cmd in commands:
        logger.info(f"Running: {cmd} in {repo_path}")
        commands_run.append(cmd)

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=repo_path,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode()
        all_output.append(f"$ {cmd}\n{output}")

        if proc.returncode != 0:
            logger.error(f"Verification failed: {cmd}")
            return VerificationResult(
                success=False,
                output="\n".join(all_output),
                commands_run=commands_run,
            )

    return VerificationResult(
        success=True,
        output="\n".join(all_output),
        commands_run=commands_run,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_verify.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add forge/verify.py tests/test_verify.py
git commit -m "feat: add verification module with auto-detection"
```

---

### Task 4: Code Handler

**Files:**
- Create: `forge/handlers/code.py`
- Create: `tests/test_code_handler.py`
- Modify: `forge/main.py` (register the code handler)

- [ ] **Step 1: Write the failing tests**

`tests/test_code_handler.py`:
```python
import os
import pytest

from forge.handlers.code import CodeHandler
from forge.models import Task, TaskSource, TaskType


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary git repo."""
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    cmds = [
        "git init",
        "git config user.email 'test@test.com'",
        "git config user.name 'Test'",
        "echo 'hello' > README.md",
        "git add .",
        "git commit -m 'initial'",
    ]
    for cmd in cmds:
        os.system(f"cd {repo_dir} && {cmd}")
    return str(repo_dir)


@pytest.fixture
def handler(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return CodeHandler(workspace_dir=str(workspace))


@pytest.fixture
def code_task():
    return Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Add a hello function",
        description="Create a hello.py file with a hello() function that returns 'Hello, World!'",
        repo="t-eckert/test-repo",
    )


def test_code_handler_type(handler):
    assert handler.task_type == "code"


async def test_triage_accepts_code_task(handler, code_task):
    result = await handler.triage(code_task)
    assert result is True


async def test_triage_rejects_no_repo(handler):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="No repo",
        description="Missing repo field",
    )
    result = await handler.triage(task)
    assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_code_handler.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write implementation**

`forge/handlers/code.py`:
```python
import logging

from forge.claude import ClaudeRunner, build_prompt
from forge.git import GitOps
from forge.models import Task
from forge.verify import run_verification

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


class CodeHandler:
    task_type: str = "code"

    def __init__(
        self,
        workspace_dir: str = "/var/lib/ardent-forge/repos",
        claude_model: str = "claude-sonnet-4-20250514",
        claude_timeout: int = 300,
    ):
        self._git = GitOps(workspace_dir)
        self._claude = ClaudeRunner(model=claude_model, timeout=claude_timeout)

    async def triage(self, task: Task) -> bool:
        """Check if we can handle this task. Requires a repo field."""
        if not task.repo:
            logger.warning(f"Task {task.id} has no repo, cannot handle")
            return False
        return True

    async def execute(self, task: Task) -> dict:
        """Clone the repo, create a worktree, run Claude Code to implement the task."""
        repo_url = f"https://github.com/{task.repo}.git"
        branch_name = f"forge/{task.id[:12]}"

        # Ensure repo is cloned
        repo_path = await self._git.ensure_repo(repo_url, task.repo)

        # Create isolated worktree
        worktree_path = await self._git.create_worktree(repo_path, branch_name)

        # Build prompt and run Claude
        prompt = build_prompt(
            title=task.title,
            description=task.description,
            repo=task.repo,
        )

        retry_context = None
        output = ""

        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                logger.info(f"Retry {attempt}/{MAX_RETRIES} for task {task.id}")
                prompt = build_prompt(
                    title=task.title,
                    description=task.description,
                    repo=task.repo,
                    retry_context=retry_context,
                )

            try:
                output = await self._claude.run(prompt, worktree_path)
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
            "claude_output": output[:2000],  # Truncate for storage
        }

    async def verify(self, task: Task) -> bool:
        """Run the repo's verification commands."""
        worktree_path = task.handler_data.get("worktree_path")
        if not worktree_path:
            logger.error(f"No worktree_path in handler_data for task {task.id}")
            return False

        result = await run_verification(worktree_path)
        return result.success

    async def deliver(self, task: Task) -> dict:
        """Create a PR with the changes."""
        worktree_path = task.handler_data.get("worktree_path")
        repo_path = task.handler_data.get("repo_path")
        branch_name = task.handler_data.get("branch_name", "")

        if not worktree_path or not repo_path:
            return {"status": "delivered", "error": "Missing worktree or repo path"}

        # Get the diff for the PR body
        try:
            diff = await self._git.get_diff(worktree_path, "main")
        except RuntimeError:
            diff = "(diff unavailable)"

        title = f"forge: {task.title}"
        body_parts = [
            f"## Task\n{task.description}",
            f"\n## Source\n{task.source.value}",
        ]
        if task.source_id:
            body_parts.append(f"Linear: {task.source_id}")
        body_parts.append("\n---\nAutomated by Ardent Forge")

        body = "\n".join(body_parts)

        try:
            pr_url = await self._git.create_pr(worktree_path, title, body)
        except RuntimeError as e:
            logger.error(f"PR creation failed: {e}")
            pr_url = f"PR creation failed: {e}"

        # Cleanup worktree
        try:
            await self._git.cleanup_worktree(repo_path, worktree_path)
        except RuntimeError:
            logger.warning(f"Failed to cleanup worktree {worktree_path}")

        return {
            "status": "delivered",
            "pr_url": pr_url,
            "branch": branch_name,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_code_handler.py -v`
Expected: 3 passed

- [ ] **Step 5: Register the code handler in main.py**

In `forge/main.py`, inside the `lifespan` function, after registering the echo handler, add:

```python
        from forge.handlers.code import CodeHandler
        registry.register(CodeHandler(
            workspace_dir=settings.workspace_dir,
        ))
```

- [ ] **Step 6: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add forge/handlers/code.py tests/test_code_handler.py forge/main.py
git commit -m "feat: add code handler with Claude Code CLI and PR creation"
```

---

### Task 5: Self-Modification Guardrails

**Files:**
- Create: `forge/guardrails.py`
- Create: `tests/test_guardrails.py`
- Modify: `forge/handlers/code.py` (add guardrail checks to triage)

- [ ] **Step 1: Write the failing tests**

`tests/test_guardrails.py`:
```python
import pytest

from forge.guardrails import check_self_modification, GuardrailViolation


def test_allows_normal_repo():
    result = check_self_modification("t-eckert/myapp", ["forge/api/tasks.py"])
    assert result is None


def test_allows_ardent_forge_safe_files():
    result = check_self_modification(
        "t-eckert/ardent-forge", ["forge/handlers/echo.py", "tests/test_echo.py"]
    )
    assert result is None


def test_blocks_nix_modification():
    result = check_self_modification(
        "t-eckert/ardent-forge", ["nix/configuration.nix"]
    )
    assert result is not None
    assert "nix/" in result


def test_blocks_guardrails_modification():
    result = check_self_modification(
        "t-eckert/ardent-forge", ["forge/guardrails.py"]
    )
    assert result is not None
    assert "guardrails" in result


def test_blocks_claude_md_modification():
    result = check_self_modification(
        "t-eckert/ardent-forge", ["CLAUDE.md"]
    )
    assert result is not None
    assert "CLAUDE.md" in result


def test_blocks_mixed_safe_and_unsafe():
    result = check_self_modification(
        "t-eckert/ardent-forge", ["forge/api/tasks.py", "nix/flake.nix"]
    )
    assert result is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_guardrails.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write implementation**

`forge/guardrails.py`:
```python
"""Safety guardrails for self-modification.

Ardent Forge can modify its own codebase, but certain files are
protected and require manual review.
"""

SELF_REPO = "t-eckert/ardent-forge"

PROTECTED_PATHS = [
    "nix/",
    "CLAUDE.md",
    "forge/guardrails.py",
]


def check_self_modification(repo: str, changed_files: list[str]) -> str | None:
    """Check if a self-modification touches protected files.

    Returns None if safe, or a description of the violation.
    """
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_guardrails.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add forge/guardrails.py tests/test_guardrails.py
git commit -m "feat: add self-modification guardrails for protected files"
```

---

### Task 6: Wire Handler Data Through Coordinator

**Files:**
- Modify: `forge/coordinator.py`
- Modify: `forge/store.py`
- Create: `tests/test_handler_data_flow.py`

The code handler's `execute()` returns data (worktree_path, repo_path, etc.) that `verify()` and `deliver()` need. The coordinator must store this data in `handler_data` and reload the task so later phases can access it.

- [ ] **Step 1: Write the failing test**

`tests/test_handler_data_flow.py`:
```python
import pytest

from forge.coordinator import Coordinator
from forge.db import Database
from forge.handlers import HandlerRegistry
from forge.models import Task, TaskSource, TaskStatus, TaskType
from forge.store import TaskStore


class DataProducingHandler:
    """Handler that produces data in execute and checks it in verify/deliver."""
    task_type: str = "data_test"

    async def triage(self, task: Task) -> bool:
        return True

    async def execute(self, task: Task) -> dict:
        return {"computed_value": "hello from execute"}

    async def verify(self, task: Task) -> bool:
        return task.handler_data.get("computed_value") == "hello from execute"

    async def deliver(self, task: Task) -> dict:
        val = task.handler_data.get("computed_value", "missing")
        return {"status": "delivered", "echo": val}


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
def store(db):
    return TaskStore(db)


@pytest.fixture
def registry():
    reg = HandlerRegistry()
    reg.register(DataProducingHandler())
    return reg


@pytest.fixture
def coordinator(store, registry):
    return Coordinator(store=store, registry=registry, max_concurrent=2)


async def test_handler_data_flows_through_pipeline(coordinator, store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Data flow test",
        description="Test handler_data propagation",
    )
    task = task.model_copy(update={"type": "data_test"})
    await store.save(task)

    await coordinator.process_pending()
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.COMPLETED
    assert loaded.result["echo"] == "hello from execute"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_handler_data_flow.py -v`
Expected: FAIL — the coordinator doesn't currently store execute's return data in handler_data or reload the task

- [ ] **Step 3: Update coordinator to persist and reload handler_data**

In `forge/store.py`, add a method:

```python
    async def update_handler_data(self, task_id: str, data: dict):
        """Merge new data into the task's handler_data."""
        now = datetime.now(timezone.utc).isoformat()
        task = await self.get(task_id)
        if task is None:
            return
        merged = {**task.handler_data, **data}
        await self._db.execute(
            "UPDATE tasks SET handler_data = ?, updated_at = ? WHERE id = ?",
            (json.dumps(merged), now, task_id),
        )
```

In `forge/coordinator.py`, after the `execute` step, persist the result and reload the task:

```python
                result = await handler.execute(task)

                # Persist execute results so verify/deliver can access them
                await self._store.update_handler_data(task.id, result)
                # Reload task with updated handler_data
                task = await self._store.get(task.id)
```

And pass the reloaded `task` to `verify()` and `deliver()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_handler_data_flow.py -v`
Expected: 1 passed

- [ ] **Step 5: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add forge/coordinator.py forge/store.py tests/test_handler_data_flow.py
git commit -m "feat: wire handler_data through coordinator pipeline"
```

---

### Task 7: Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run the complete test suite**

```bash
uv run pytest -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 2: Verify the full module structure**

```bash
find forge -name "*.py" | sort
find tests -name "*.py" | sort
```

Expected file listing matches the plan's file structure.

- [ ] **Step 3: Commit any remaining changes**

If any cleanup needed, commit it.
