"""/api/tasks — task CRUD + filters."""

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
