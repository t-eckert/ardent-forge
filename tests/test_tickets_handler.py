from forge.agents.tickets import parse_plan_tasks
from forge.agents import AgentContext

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


ctx = AgentContext(tools=[], store=None, settings=None)


def test_parse_plan_tasks_returns_one_per_task_header():
    tasks = parse_plan_tasks(PLAN_SAMPLE)
    assert len(tasks) == 2
    assert tasks[0].number == 1
    assert tasks[0].title == "First thing"
    assert "do a" in tasks[0].body
    assert tasks[1].number == 2
    assert tasks[1].title == "Second thing"
    assert "do b" in tasks[1].body
    assert "do b" not in tasks[0].body


def test_parse_plan_tasks_empty_when_no_headers():
    assert parse_plan_tasks("# Nothing here\n\nJust text.") == []


from pathlib import Path
from unittest.mock import AsyncMock


from forge.agents.tickets import (
    TicketsAgent,
    extract_plan_path,
    extract_spec_path_from_tickets_task,
)
from forge.agents import AgentContext
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
    assert (
        extract_plan_path("plan: docs/superpowers/plans/2026-04-15-foo.md")
        == "docs/superpowers/plans/2026-04-15-foo.md"
    )
    assert extract_plan_path("nothing") is None


def test_extract_spec_path_from_tickets_task():
    assert (
        extract_spec_path_from_tickets_task("spec: docs/superpowers/specs/2026-04-15-foo.md")
        == "docs/superpowers/specs/2026-04-15-foo.md"
    )
    assert extract_spec_path_from_tickets_task("none") is None


async def test_tickets_triage_requires_plan_path():
    handler = TicketsAgent(workspace_dir="/tmp/w", linear=AsyncMock(), team_id="t1")
    assert await handler.triage(_ticket_task("plan: docs/superpowers/plans/x.md"), ctx) is True
    assert await handler.triage(_ticket_task("no"), ctx) is False


async def test_tickets_execute_creates_project_and_issues(tmp_path: Path):
    repo = tmp_path / "repo"
    plans = repo / "docs" / "superpowers" / "plans"
    specs = repo / "docs" / "superpowers" / "specs"
    plans.mkdir(parents=True)
    specs.mkdir(parents=True)
    (plans / "2026-04-15-foo.md").write_text(
        "# Foo Plan\n\n## Task 1: One\n\nbody1\n\n## Task 2: Two\n\nbody2\n"
    )
    (specs / "2026-04-15-foo.md").write_text("---\nstatus: planned\ntitle: Foo\n---\n\nbody\n")

    linear = AsyncMock()
    linear.create_project = AsyncMock(return_value=("p1", "https://linear.app/x/p1"))
    linear.get_label_id = AsyncMock(return_value="lab-devagent")
    linear.create_issue = AsyncMock(
        side_effect=[
            ("i1", "FORGE-1", "u1"),
            ("i2", "FORGE-2", "u2"),
        ]
    )

    handler = TicketsAgent(
        workspace_dir="/tmp/w",
        linear=linear,
        team_id="t1",
        self_repo="t-eckert/ardent-forge",
    )
    handler._git.ensure_repo = AsyncMock(return_value=str(repo))
    handler._git._run = AsyncMock(return_value="")

    task = _ticket_task(
        "plan: docs/superpowers/plans/2026-04-15-foo.md spec: docs/superpowers/specs/2026-04-15-foo.md"
    )
    result = await handler.execute(task, ctx)

    assert result["project_id"] == "p1"
    assert result["issue_identifiers"] == ["FORGE-1", "FORGE-2"]
    linear.create_project.assert_awaited_once()
    assert linear.create_issue.await_count == 2
    from forge.frontmatter import read_spec, SpecStatus

    parsed = read_spec(specs / "2026-04-15-foo.md")
    assert parsed.status == SpecStatus.EXECUTING


async def test_tickets_execute_resets_to_origin_main_before_reading(tmp_path: Path):
    """execute() must reset the working tree to origin/main before reading files."""
    repo = tmp_path / "repo"
    plans = repo / "docs" / "superpowers" / "plans"
    specs = repo / "docs" / "superpowers" / "specs"
    plans.mkdir(parents=True)
    specs.mkdir(parents=True)
    (plans / "2026-04-15-foo.md").write_text("# Foo Plan\n\n## Task 1: One\n\nbody1\n")
    (specs / "2026-04-15-foo.md").write_text("---\nstatus: planned\ntitle: Foo\n---\n\nbody\n")

    linear = AsyncMock()
    linear.create_project = AsyncMock(return_value=("p1", "https://linear.app/x/p1"))
    linear.get_label_id = AsyncMock(return_value=None)
    linear.create_issue = AsyncMock(return_value=("i1", "FORGE-1", "u1"))

    handler = TicketsAgent(
        workspace_dir="/tmp/w",
        linear=linear,
        team_id="t1",
        self_repo="t-eckert/ardent-forge",
    )
    handler._git.ensure_repo = AsyncMock(return_value=str(repo))
    handler._git._run = AsyncMock(return_value="")

    task = _ticket_task(
        "plan: docs/superpowers/plans/2026-04-15-foo.md spec: docs/superpowers/specs/2026-04-15-foo.md"
    )
    await handler.execute(task, ctx)

    run_calls = [call[0][0] for call in handler._git._run.call_args_list]
    assert any("fetch origin main" in c for c in run_calls), "missing: git fetch origin main"
    assert any("checkout main" in c for c in run_calls), "missing: git checkout main"
    assert any("reset --hard origin/main" in c for c in run_calls), (
        "missing: git reset --hard origin/main"
    )

    # Verify the fetch/checkout/reset appear before any subsequent file-reading step
    fetch_idx = next(i for i, c in enumerate(run_calls) if "fetch origin main" in c)
    checkout_idx = next(i for i, c in enumerate(run_calls) if "checkout main" in c)
    reset_idx = next(i for i, c in enumerate(run_calls) if "reset --hard origin/main" in c)
    assert fetch_idx < checkout_idx < reset_idx


async def test_tickets_deliver_uses_working_tree_changes():
    """deliver() must call get_working_tree_changes, not get_changed_files."""
    handler = TicketsAgent(
        workspace_dir="/tmp/w",
        linear=AsyncMock(),
        team_id="t1",
        self_repo="t-eckert/ardent-forge",
    )
    handler._git.get_working_tree_changes = AsyncMock(
        return_value=["docs/superpowers/specs/2026-04-15-foo.md"]
    )
    handler._git.commit_all = AsyncMock(return_value=None)
    handler._git._run = AsyncMock(return_value="")

    task = _ticket_task("plan: docs/superpowers/plans/x.md spec: docs/superpowers/specs/x.md")
    task.handler_data = {
        "repo_path": "/tmp/repo",
        "spec_path": "docs/superpowers/specs/2026-04-15-foo.md",
        "project_url": "https://linear.app/x/p1",
        "issue_identifiers": ["FORGE-1"],
    }
    result = await handler.deliver(task, ctx)

    handler._git.get_working_tree_changes.assert_awaited_once_with("/tmp/repo")
    assert result["status"] == "delivered"
