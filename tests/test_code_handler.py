import os
import pytest

from forge.handlers.code import CodeHandler
from forge.models import Task, TaskSource, TaskType


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
