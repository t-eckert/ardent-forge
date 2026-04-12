from pathlib import Path

import pytest

from forge.handlers.plan import PlanHandler, build_plan_prompt, extract_spec_path
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


def test_extract_spec_path_pulls_spec_from_description():
    assert extract_spec_path("spec: docs/superpowers/specs/2026-04-15-foo.md") == "docs/superpowers/specs/2026-04-15-foo.md"
    assert extract_spec_path("no spec") is None


from unittest.mock import AsyncMock


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
