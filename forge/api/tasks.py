from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from forge.models import Task, TaskSource, TaskStatus, TaskType
from forge.store import TaskStore

router = APIRouter(prefix="/api/tasks")

_store: TaskStore | None = None


def set_store(store: TaskStore):
    global _store
    _store = store


def get_store() -> TaskStore:
    assert _store is not None
    return _store


class CreateTaskRequest(BaseModel):
    type: str
    title: str
    description: str
    repo: str | None = None
    source_id: str | None = None


@router.post("", status_code=201)
async def create_task(req: CreateTaskRequest):
    store = get_store()
    task = Task.new(
        task_type=TaskType(req.type) if req.type in TaskType.__members__.values() else req.type,
        source=TaskSource.CHAT,
        title=req.title,
        description=req.description,
        repo=req.repo,
        source_id=req.source_id,
    )
    await store.save(task)
    return task.model_dump(mode="json")


@router.get("/{task_id}")
async def get_task(task_id: str):
    store = get_store()
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.model_dump(mode="json")


@router.get("")
async def list_tasks(status: str | None = None):
    store = get_store()
    if status:
        tasks = await store.list_by_status(TaskStatus(status))
    else:
        tasks = await store.list_by_status(TaskStatus.QUEUED)
        for s in [TaskStatus.TRIAGING, TaskStatus.EXECUTING, TaskStatus.VERIFYING,
                   TaskStatus.DELIVERING, TaskStatus.COMPLETED, TaskStatus.FAILED]:
            tasks.extend(await store.list_by_status(s))
    return [t.model_dump(mode="json") for t in tasks]
