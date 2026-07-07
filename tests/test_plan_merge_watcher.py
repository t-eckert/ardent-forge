from pathlib import Path
from unittest.mock import AsyncMock


from forge.models import TaskType
from forge.watchers.plan_merge_watcher import PlanMergeWatcher


class FakeStore:
    def __init__(self):
        self.saved = []
        self.existing_ids: set[str] = set()

    async def find_by_source_id(self, sid):
        return "exists" if sid in self.existing_ids else None

    async def save(self, task):
        self.saved.append(task)


async def test_enqueues_tickets_when_plan_and_planned_spec_present(tmp_path: Path):
    repo = tmp_path / "repo"
    plans = repo / "docs" / "superpowers" / "plans"
    specs = repo / "docs" / "superpowers" / "specs"
    plans.mkdir(parents=True)
    specs.mkdir(parents=True)
    (plans / "2026-04-15-foo.md").write_text("# Plan\n## Task 1: x\n\nbody\n")
    (specs / "2026-04-15-foo.md").write_text("---\nstatus: planned\n---\n\nbody\n")

    store = FakeStore()
    watcher = PlanMergeWatcher(
        store=store,
        repo_path=str(repo),
        fetch_fn=AsyncMock(),
    )
    created = await watcher.poll()
    assert created == 1
    task = store.saved[0]
    assert task.type == TaskType.TICKETS
    assert "plan: docs/superpowers/plans/2026-04-15-foo.md" in task.description
    assert "spec: docs/superpowers/specs/2026-04-15-foo.md" in task.description


async def test_skips_when_no_matching_spec(tmp_path: Path):
    repo = tmp_path / "repo"
    plans = repo / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / "2026-04-15-foo.md").write_text("# Plan\n")
    store = FakeStore()
    watcher = PlanMergeWatcher(store=store, repo_path=str(repo), fetch_fn=AsyncMock())
    created = await watcher.poll()
    assert created == 0


async def test_deduplicates(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (repo / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (repo / "docs" / "superpowers" / "plans" / "2026-04-15-foo.md").write_text("# P\n")
    (repo / "docs" / "superpowers" / "specs" / "2026-04-15-foo.md").write_text(
        "---\nstatus: planned\n---\n\n"
    )
    store = FakeStore()
    store.existing_ids.add("plan:docs/superpowers/plans/2026-04-15-foo.md")
    watcher = PlanMergeWatcher(store=store, repo_path=str(repo), fetch_fn=AsyncMock())
    assert await watcher.poll() == 0
