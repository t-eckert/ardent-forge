from datetime import datetime, timedelta, timezone

from forge.models import Task, TaskSource, TaskStatus, TaskType
from forge.worktree_reaper import reapable_worktrees


def _task(status, updated_at, worktree_path, repo_path="/repo"):
    t = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d")
    t = t.model_copy(update={
        "status": status,
        "updated_at": updated_at,
        "handler_data": {"worktree_path": worktree_path, "repo_path": repo_path},
    })
    return t


def test_reaps_terminal_worktree_past_ttl():
    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=72)
    tasks = [_task(TaskStatus.COMPLETED, old, "/repo/.worktrees/forge/a")]
    result = reapable_worktrees(tasks, now, timedelta(hours=48))
    assert result == [("/repo", "/repo/.worktrees/forge/a")]


def test_keeps_recent_terminal_worktree():
    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    recent = now - timedelta(hours=1)
    tasks = [_task(TaskStatus.COMPLETED, recent, "/repo/.worktrees/forge/a")]
    assert reapable_worktrees(tasks, now, timedelta(hours=48)) == []


def test_keeps_worktree_with_active_reference():
    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=72)
    tasks = [
        _task(TaskStatus.COMPLETED, old, "/repo/.worktrees/forge/a"),
        _task(TaskStatus.EXECUTING, old, "/repo/.worktrees/forge/a"),
    ]
    assert reapable_worktrees(tasks, now, timedelta(hours=48)) == []


def test_awaiting_approval_keeps_worktree():
    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=72)
    tasks = [_task(TaskStatus.AWAITING_APPROVAL, old, "/repo/.worktrees/forge/a")]
    assert reapable_worktrees(tasks, now, timedelta(hours=48)) == []


def test_shared_worktree_kept_alive_by_recent_followup():
    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=72)
    recent = now - timedelta(hours=2)
    wt = "/repo/.worktrees/forge/a"
    tasks = [
        _task(TaskStatus.COMPLETED, old, wt),     # parent, old
        _task(TaskStatus.COMPLETED, recent, wt),  # follow-up, recent
    ]
    assert reapable_worktrees(tasks, now, timedelta(hours=48)) == []


def test_skips_group_without_repo_path():
    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=72)
    t = Task.new(task_type=TaskType.CODE, source=TaskSource.MANUAL, title="t", description="d")
    t = t.model_copy(update={
        "status": TaskStatus.COMPLETED,
        "updated_at": old,
        "handler_data": {"worktree_path": "/repo/.worktrees/forge/a"},  # no repo_path
    })
    assert reapable_worktrees([t], now, timedelta(hours=48)) == []


def test_queued_followup_protects_worktree():
    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=72)
    wt = "/repo/.worktrees/forge/a"
    parent = _task(TaskStatus.COMPLETED, old, wt)
    followup = _task(TaskStatus.QUEUED, old, wt)  # queued, shares the worktree
    assert reapable_worktrees([parent, followup], now, timedelta(hours=48)) == []
