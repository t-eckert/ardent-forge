from pathlib import Path
from unittest.mock import AsyncMock


from forge.frontmatter import SpecStatus, read_spec, update_spec_status
from forge.agents.tickets import TicketsAgent
from forge.agents import AgentContext

ctx = AgentContext(tools=[], store=None, settings=None)
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

    spec_watcher = SpecWatcher(store=store, repo_path=str(repo), fetch_fn=AsyncMock())
    plan_merge_watcher = PlanMergeWatcher(store=store, repo_path=str(repo), fetch_fn=AsyncMock())

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
    linear.create_issue = AsyncMock(
        side_effect=[
            ("i1", "FORGE-1", "u1"),
            ("i2", "FORGE-2", "u2"),
        ]
    )
    handler = TicketsAgent(
        workspace_dir=str(tmp_path / "ws"),
        linear=linear,
        team_id="t1",
    )
    handler._git.ensure_repo = AsyncMock(return_value=str(repo))
    handler._git._run = AsyncMock(return_value="")
    result = await handler.execute(tickets_task, ctx)

    assert result["issue_identifiers"] == ["FORGE-1", "FORGE-2"]
    assert read_spec(spec_file).status == SpecStatus.EXECUTING

    # 5. Re-polling does not duplicate
    assert await spec_watcher.poll() == 0
    assert await plan_merge_watcher.poll() == 0
