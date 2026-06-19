"""Pure decision logic for reclaiming Code-task git worktrees.

Worktrees persist after delivery so follow-up tasks can `claude --continue` in
them. A worktree is reclaimable only when *every* task referencing it is terminal
and the most recently touched reference is older than the retention TTL. Grouping
by path keeps a shared worktree alive while any parent or recent follow-up still
references it.
"""

from datetime import datetime, timedelta

from forge.models import Task, TaskStatus

# A worktree referenced by any task in one of these states must not be reclaimed.
ACTIVE_STATES = {
    TaskStatus.QUEUED,
    TaskStatus.TRIAGING,
    TaskStatus.EXECUTING,
    TaskStatus.VERIFYING,
    TaskStatus.DELIVERING,
    TaskStatus.AWAITING_APPROVAL,
}


def reapable_worktrees(
    tasks: list[Task], now: datetime, ttl: timedelta
) -> list[tuple[str, str]]:
    """Return (repo_path, worktree_path) pairs whose worktree can be removed."""
    groups: dict[str, list[Task]] = {}
    for task in tasks:
        wt = (task.handler_data or {}).get("worktree_path")
        if wt:
            groups.setdefault(wt, []).append(task)

    reapable: list[tuple[str, str]] = []
    for worktree_path, group in groups.items():
        if any(t.status in ACTIVE_STATES for t in group):
            continue
        newest = max(t.updated_at for t in group)
        if now - newest <= ttl:
            continue
        repo_path = next(
            (rp for t in group if (rp := (t.handler_data or {}).get("repo_path"))),
            None,
        )
        if repo_path:
            reapable.append((repo_path, worktree_path))
    return reapable
