from pathlib import Path

import pytest

from forge.agents.plan import PlanAgent, build_plan_prompt, extract_spec_path
from forge.agents import AgentContext
from forge.models import Task, TaskSource, TaskType



ctx = AgentContext(tools=[], store=None, settings=None)


def _task(description: str = "spec: docs/superpowers/specs/2026-04-15-foo.md") -> Task:
    return Task.new(
        task_type=TaskType.PLAN,
        source=TaskSource.WEBHOOK,
        title="plan spec",
        description=description,
        repo="t-eckert/ardent-forge",
    )


async def test_triage_accepts_task_with_spec_path_in_description():
    handler = PlanAgent(workspace_dir="/tmp/wsp", specs_dir="docs/superpowers/specs")
    assert await handler.triage(_task(), ctx) is True


async def test_triage_rejects_task_without_spec_path():
    handler = PlanAgent(workspace_dir="/tmp/wsp", specs_dir="docs/superpowers/specs")
    task = _task(description="no spec here")
    assert await handler.triage(task, ctx) is False


def test_build_plan_prompt_mentions_spec_and_format():
    spec_text = "# My Spec\n\nBuild a widget."
    prompt = build_plan_prompt(spec_path="docs/superpowers/specs/foo.md", spec_body=spec_text)
    assert "# My Spec" in prompt
    assert "docs/superpowers/plans/" in prompt
    assert "numbered" in prompt.lower()


def test_extract_spec_path_pulls_spec_from_description():
    assert extract_spec_path("spec: docs/superpowers/specs/2026-04-15-foo.md") == "docs/superpowers/specs/2026-04-15-foo.md"
    assert extract_spec_path("no spec") is None


from unittest.mock import AsyncMock


async def test_execute_clones_creates_worktree_and_invokes_claude(tmp_path):
    handler = PlanAgent(workspace_dir=str(tmp_path / "ws"))

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
    result = await handler.execute(task, ctx)

    assert result["worktree_path"] == str(worktree_path)
    assert result["spec_path"] == "docs/superpowers/specs/2026-04-15-foo.md"
    assert result["branch_name"].startswith("forge/plan-")
    handler._claude.run.assert_awaited_once()


async def test_verify_passes_when_diff_is_plan_and_spec_only():
    handler = PlanAgent(workspace_dir="/tmp/wsp")
    handler._git.get_working_tree_changes = AsyncMock(return_value=[
        "docs/superpowers/plans/2026-04-15-foo.md",
        "docs/superpowers/specs/2026-04-15-foo.md",
    ])
    task = _task()
    task.handler_data = {"worktree_path": "/tmp/wt"}
    assert await handler.verify(task, ctx) is True


async def test_verify_fails_when_diff_touches_code():
    handler = PlanAgent(workspace_dir="/tmp/wsp")
    handler._git.get_working_tree_changes = AsyncMock(return_value=[
        "docs/superpowers/plans/2026-04-15-foo.md",
        "forge/main.py",
    ])
    task = _task()
    task.handler_data = {"worktree_path": "/tmp/wt"}
    assert await handler.verify(task, ctx) is False


async def test_verify_fails_when_no_worktree():
    handler = PlanAgent(workspace_dir="/tmp/wsp")
    task = _task()
    task.handler_data = {}
    assert await handler.verify(task, ctx) is False


async def test_deliver_commits_opens_pr_and_returns_url():
    handler = PlanAgent(workspace_dir="/tmp/wsp")
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
    result = await handler.deliver(task, ctx)

    assert result["status"] == "delivered"
    assert result["pr_url"] == "https://github.com/x/y/pull/1"
    handler._git.commit_all.assert_awaited_once()
    handler._git.create_pr.assert_awaited_once()
