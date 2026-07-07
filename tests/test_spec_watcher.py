from pathlib import Path
from unittest.mock import AsyncMock


from forge.models import TaskSource, TaskType
from forge.watchers.spec_watcher import SpecWatcher


class FakeStore:
    def __init__(self):
        self.saved = []
        self.existing_ids: set[str] = set()

    async def find_by_source_id(self, sid):
        return "exists" if sid in self.existing_ids else None

    async def save(self, task):
        self.saved.append(task)


async def test_spec_watcher_enqueues_ready_specs(tmp_path: Path):
    specs_dir = tmp_path / "repo" / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "2026-04-15-a.md").write_text(
        "---\nstatus: ready-to-plan\ntitle: A\n---\n\nBody\n"
    )
    (specs_dir / "2026-04-15-b.md").write_text("---\nstatus: draft\n---\n\nBody\n")

    store = FakeStore()
    fetch = AsyncMock()
    watcher = SpecWatcher(
        store=store,
        repo_path=str(tmp_path / "repo"),
        specs_subdir="docs/superpowers/specs",
        fetch_fn=fetch,
    )
    created = await watcher.poll()

    assert created == 1
    assert len(store.saved) == 1
    task = store.saved[0]
    assert task.type == TaskType.PLAN
    assert task.source == TaskSource.WEBHOOK
    assert task.source_id == "spec:docs/superpowers/specs/2026-04-15-a.md"
    assert "docs/superpowers/specs/2026-04-15-a.md" in task.description
    fetch.assert_awaited_once()


async def test_spec_watcher_deduplicates(tmp_path: Path):
    specs_dir = tmp_path / "repo" / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "2026-04-15-a.md").write_text("---\nstatus: ready-to-plan\n---\n\nBody\n")
    store = FakeStore()
    store.existing_ids.add("spec:docs/superpowers/specs/2026-04-15-a.md")

    watcher = SpecWatcher(
        store=store,
        repo_path=str(tmp_path / "repo"),
        specs_subdir="docs/superpowers/specs",
        fetch_fn=AsyncMock(),
    )
    created = await watcher.poll()
    assert created == 0
    assert store.saved == []
