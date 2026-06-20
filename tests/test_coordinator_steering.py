import pytest
from forge.coordinator import Coordinator
from forge.agents import AgentRegistry
from forge.models import Task, TaskType, TaskSource, TaskStatus
from forge.store import TaskStore
from forge.db import Database


class FullAgent:
    name = "full"
    task_type = "code"
    stages = ["execute", "verify", "deliver"]
    connectors: list = []
    timeout_seconds = 60

    async def execute(self, task, ctx):
        return {"executed": True}

    async def verify(self, task, ctx):
        return True

    async def deliver(self, task, ctx):
        return {"delivered": True}


@pytest.fixture
async def setup():
    db = Database(":memory:")
    await db.initialize()
    store = TaskStore(db)
    registry = AgentRegistry()
    registry.register(FullAgent())
    coord = Coordinator(store=store, registry=registry, connectors=None, settings=None, max_concurrent=2)
    yield store, coord
    await db.close()


async def test_require_approval_parks_before_deliver(setup):
    store, coord = setup
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d", require_approval=True)
    await store.save(task)
    await coord.process_pending()
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.AWAITING_APPROVAL
    assert "delivered" not in (loaded.handler_data or {})


async def test_no_approval_completes_normally(setup):
    store, coord = setup
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d")
    await store.save(task)
    await coord.process_pending()
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.COMPLETED


async def test_resume_delivers_approved_task(setup):
    store, coord = setup
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d", require_approval=True)
    await store.save(task)
    await coord.process_pending()  # parks
    assert (await store.get(task.id)).status == TaskStatus.AWAITING_APPROVAL
    await store.mark_approved(task.id)  # -> delivering
    await coord.resume_approved_deliveries()
    loaded = await store.get(task.id)
    assert loaded.status == TaskStatus.COMPLETED
    assert loaded.result.get("delivered") is True


class FailDeliverAgent:
    """execute+verify ok, deliver raises — to exercise resume error handling."""
    name = "faildeliver"
    task_type = "code"
    stages = ["execute", "verify", "deliver"]
    connectors: list = []
    timeout_seconds = 60

    async def execute(self, task, ctx):
        return {"executed": True}

    async def verify(self, task, ctx):
        return True

    async def deliver(self, task, ctx):
        raise RuntimeError("deliver boom")


async def test_resume_deliver_failure_retries_not_terminal():
    # A transient deliver failure on the resume path must preserve the retry
    # budget (requeue), mirroring the normal pipeline — not fail terminally.
    db = Database(":memory:")
    await db.initialize()
    store = TaskStore(db)
    registry = AgentRegistry()
    registry.register(FailDeliverAgent())
    coord = Coordinator(store=store, registry=registry, connectors=None, settings=None, max_concurrent=2)
    try:
        task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d", require_approval=True)
        await store.save(task)
        await coord.process_pending()  # parks at awaiting_approval
        await store.mark_approved(task.id)  # -> delivering
        await coord.resume_approved_deliveries()  # deliver raises
        loaded = await store.get(task.id)
        # retry.TRANSIENT with budget remaining => requeued, not terminally failed
        assert loaded.status == TaskStatus.QUEUED
    finally:
        await db.close()


from datetime import datetime, timedelta, timezone


class _RecordingGit:
    def __init__(self):
        self.removed = []
        self.pruned = []

    async def cleanup_worktree(self, repo_path, worktree_path):
        self.removed.append((repo_path, worktree_path))

    async def prune_worktrees(self, repo_path):
        self.pruned.append(repo_path)


async def test_reap_old_worktrees_removes_stale(setup, tmp_path):
    store, coord = setup
    git = _RecordingGit()
    coord._git = git
    coord._worktree_ttl = timedelta(hours=48)

    repo_path = str(tmp_path / "repo")
    wt = tmp_path / "repo" / ".worktrees" / "forge" / "a"
    wt.mkdir(parents=True)  # real dir so the isdir guard passes
    worktree_path = str(wt)

    old = datetime.now(timezone.utc) - timedelta(hours=72)
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d")
    task = task.model_copy(update={
        "status": TaskStatus.COMPLETED,
        "updated_at": old,
        "handler_data": {"worktree_path": worktree_path, "repo_path": repo_path},
    })
    await store.save(task)
    await store._db.execute(
        "UPDATE tasks SET updated_at = ? WHERE id = ?", (old.isoformat(), task.id)
    )

    n = await coord.reap_old_worktrees()
    assert n == 1
    assert git.removed == [(repo_path, worktree_path)]
    assert git.pruned == [repo_path]


async def test_reap_old_worktrees_skips_missing_dir(setup, tmp_path):
    store, coord = setup
    git = _RecordingGit()
    coord._git = git
    coord._worktree_ttl = timedelta(hours=48)

    # worktree_path points at a directory that does not exist (already cleaned up).
    missing = str(tmp_path / "gone")
    old = datetime.now(timezone.utc) - timedelta(hours=72)
    task = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d")
    task = task.model_copy(update={
        "status": TaskStatus.COMPLETED,
        "updated_at": old,
        "handler_data": {"worktree_path": missing, "repo_path": str(tmp_path)},
    })
    await store.save(task)
    await store._db.execute(
        "UPDATE tasks SET updated_at = ? WHERE id = ?", (old.isoformat(), task.id)
    )

    n = await coord.reap_old_worktrees()
    assert n == 0
    assert git.removed == []  # nothing attempted for an already-gone worktree


async def test_reap_old_worktrees_noop_without_git(setup):
    store, coord = setup
    coord._git = None
    assert await coord.reap_old_worktrees() == 0
