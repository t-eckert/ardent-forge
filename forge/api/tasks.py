"""/api/tasks — task CRUD + filters."""

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from forge.models import Task, TaskSource, TaskStatus, TaskType
from forge.store import TaskStore
from forge.zellij import kill_session

router = APIRouter(prefix="/api/tasks")

_store: TaskStore | None = None


def set_store(store: TaskStore):
    global _store
    _store = store


def get_store() -> TaskStore:
    assert _store is not None
    return _store


_coordinator: object | None = None


def set_coordinator(coordinator: object) -> None:
    global _coordinator
    _coordinator = coordinator


def _task_dict(task: Task) -> dict:
    return task.model_dump(mode="json")


class CreateTaskRequest(BaseModel):
    type: str = Field(max_length=64)
    title: str = Field(max_length=500)
    description: str = Field(max_length=50_000)
    repo: str | None = Field(default=None, max_length=500)
    source_id: str | None = Field(default=None, max_length=200)
    require_approval: bool = False


class FollowUpRequest(BaseModel):
    prompt: str = Field(max_length=50_000)


@router.post("", status_code=201)
async def create_task(req: CreateTaskRequest):
    store = get_store()
    task = Task.new(
        task_type=(
            TaskType(req.type)
            if req.type in TaskType.__members__.values()
            else req.type
        ),
        source=TaskSource.MANUAL,
        title=req.title,
        description=req.description,
        repo=req.repo,
        source_id=req.source_id,
        require_approval=req.require_approval,
    )
    await store.save(task)

    if _coordinator is not None and hasattr(_coordinator, "nudge"):
        _coordinator.nudge()

    return _task_dict(task)


@router.post("/{task_id}/retry")
async def retry_task(task_id: str):
    """Manually requeue a FAILED task with a fresh retry budget, running it
    immediately (ignoring backoff). Kills any lingering Zellij session first."""
    store = get_store()
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.FAILED:
        raise HTTPException(
            status_code=409,
            detail=f"Only failed tasks can be retried (status={task.status.value})",
        )

    session = (task.handler_data or {}).get("zellij_session")
    if session:
        await kill_session(session)

    await store.clear_for_retry(task_id)
    updated = await store.get(task_id)
    return _task_dict(updated)


_TERMINAL = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}

_FOLLOW_UP_OK = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.AWAITING_APPROVAL}


async def _kill_session_if_any(task) -> None:
    session = (task.handler_data or {}).get("zellij_session")
    if session:
        await kill_session(session)


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    store = get_store()
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in _TERMINAL:
        raise HTTPException(status_code=409, detail=f"Cannot cancel a {task.status.value} task")
    await _kill_session_if_any(task)
    await store.mark_cancelled(task_id)
    return _task_dict(await store.get(task_id))


@router.post("/{task_id}/approve")
async def approve_task(task_id: str):
    store = get_store()
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.AWAITING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Only awaiting_approval tasks can be approved (status={task.status.value})")
    await store.mark_approved(task_id)
    if _coordinator is not None and hasattr(_coordinator, "nudge"):
        _coordinator.nudge()
    return _task_dict(await store.get(task_id))


@router.post("/{task_id}/reject")
async def reject_task(task_id: str):
    store = get_store()
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.AWAITING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Only awaiting_approval tasks can be rejected (status={task.status.value})")
    await _kill_session_if_any(task)
    await store.mark_cancelled(task_id)
    return _task_dict(await store.get(task_id))


@router.post("/{task_id}/follow-up")
async def follow_up_task(task_id: str, req: FollowUpRequest):
    """Queue a continuation of a finished Code task. The new task reuses the
    parent's worktree + Claude conversation (`claude --continue`)."""
    store = get_store()
    parent = await store.get(task_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if str(parent.type) != "code":
        raise HTTPException(status_code=409, detail="Only code tasks support follow-up")
    if parent.status not in _FOLLOW_UP_OK:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot follow up a {parent.status.value} task",
        )
    worktree_path = (parent.handler_data or {}).get("worktree_path")
    if not worktree_path or not os.path.isdir(worktree_path):
        raise HTTPException(
            status_code=409,
            detail="Parent worktree no longer available; it was reaped",
        )

    title = (req.prompt[:80] + "…") if len(req.prompt) > 80 else req.prompt
    follow_up = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.MANUAL,
        title=f"Follow-up: {title}",
        description=req.prompt,
        repo=parent.repo,
        require_approval=parent.require_approval,
        continues_task_id=parent.id,
    )
    await store.save(follow_up)

    if _coordinator is not None and hasattr(_coordinator, "nudge"):
        _coordinator.nudge()

    return _task_dict(follow_up)


@router.get("/{task_id}")
async def get_task(task_id: str):
    store = get_store()
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_dict(task)


@router.get("")
async def list_tasks(
    status: str | None = None,
    type: str | None = None,
    completed_since: str | None = None,
):
    store = get_store()
    if completed_since:
        tasks = await store.list_completed_since(completed_since)
    elif status:
        tasks = await store.list_by_status(TaskStatus(status))
    else:
        tasks = await store.list_all()
    if type:
        tasks = [t for t in tasks if t.type == type]

    return [_task_dict(t) for t in tasks]
