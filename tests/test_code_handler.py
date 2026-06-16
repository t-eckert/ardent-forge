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
