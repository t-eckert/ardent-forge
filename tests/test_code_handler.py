import os
import pytest
from unittest.mock import AsyncMock, patch

from forge.agents.code import CodeAgent
from forge.agents import AgentContext
from forge.models import Task, TaskSource, TaskType
from forge.store import TaskStore
from forge.verify import VerificationResult, VerificationStatus



ctx = AgentContext(tools=[], store=None, settings=None)


@pytest.fixture
def temp_repo(tmp_path):
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
    return CodeAgent(workspace_dir=str(workspace))


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
    result = await handler.triage(code_task, ctx)
    assert result is True


async def test_triage_rejects_no_repo(handler):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="No repo",
        description="Missing repo field",
    )
    result = await handler.triage(task, ctx)
    assert result is False


async def _verify_task(store: TaskStore, worktree: str) -> Task:
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="t",
        description="d",
        repo="x/y",
    )
    await store.save(task)
    await store.update_handler_data(task.id, {"worktree_path": worktree})
    return await store.get(task.id)


async def test_verify_records_inconclusive_and_blocks(db, handler, tmp_path):
    store = TaskStore(db)
    task = await _verify_task(store, str(tmp_path))
    vctx = AgentContext(tools=[], store=store, settings=None)
    fake = VerificationResult(
        success=False,
        output="",
        commands_run=["uv run pytest -v"],
        status=VerificationStatus.INCONCLUSIVE,
    )
    with patch("forge.agents.code.run_verification", AsyncMock(return_value=fake)):
        ok = await handler.verify(task, vctx)
    assert ok is False
    reloaded = await store.get(task.id)
    assert reloaded.handler_data["verification"]["status"] == "inconclusive"
    assert reloaded.handler_data["verification"]["commands_run"] == ["uv run pytest -v"]


async def test_verify_records_passed_and_allows(db, handler, tmp_path):
    store = TaskStore(db)
    task = await _verify_task(store, str(tmp_path))
    vctx = AgentContext(tools=[], store=store, settings=None)
    fake = VerificationResult(
        success=True,
        output="",
        commands_run=["uv run pytest -v"],
        status=VerificationStatus.PASSED,
    )
    with patch("forge.agents.code.run_verification", AsyncMock(return_value=fake)):
        ok = await handler.verify(task, vctx)
    assert ok is True
    reloaded = await store.get(task.id)
    assert reloaded.handler_data["verification"]["status"] == "passed"


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


async def test_deliver_existing_pr_push_failure_surfaces_error(handler, tmp_path):
    class _PushFailGit(_FakeGit):
        async def push_branch(self, worktree_path):
            raise RuntimeError("remote: permission denied")

    fake = _PushFailGit(existing_pr="https://github.com/o/r/pull/9")
    handler._git = fake
    task = _delivery_task(tmp_path)
    result = await handler.deliver(task, ctx)
    # Delivery does not raise; PR URL is still returned...
    assert result["pr_url"] == "https://github.com/o/r/pull/9"
    # ...but the push failure is surfaced in the result for the operator.
    assert "permission denied" in result["push_error"]


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
