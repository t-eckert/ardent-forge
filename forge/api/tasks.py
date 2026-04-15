"""/api/tasks — task CRUD + filters + origin/referencing thread joins.

Extended in Phase F for the UI reframe: adds type filter, origin_thread_id
to each dict, and a detail payload that includes the referencing thread ids.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from forge.models import Task, TaskSource, TaskStatus, TaskType
from forge.store import TaskStore
from forge.thread_store import ThreadStore

router = APIRouter(prefix="/api/tasks")

_store: TaskStore | None = None


def set_store(store: TaskStore):
    global _store
    _store = store


def get_store() -> TaskStore:
    assert _store is not None
    return _store


def _thread_store(request: Request) -> ThreadStore | None:
    return getattr(request.app.state, "thread_store", None)


async def _task_dict(task: Task, thread_store: ThreadStore | None) -> dict:
    out = task.model_dump(mode="json")
    if thread_store is not None:
        out["origin_thread_id"] = await thread_store.origin_thread_for(task.id)
    return out


class CreateTaskRequest(BaseModel):
    type: str
    title: str
    description: str
    repo: str | None = None
    source_id: str | None = None
    # Optional: link this task to an origin thread at creation time. Used by
    # Forge's task-dispatch turns so the coordinator knows where to post
    # the resolution message on completion.
    origin_thread_id: str | None = None


@router.post("", status_code=201)
async def create_task(req: CreateTaskRequest, request: Request):
    store = get_store()
    task = Task.new(
        task_type=(
            TaskType(req.type)
            if req.type in TaskType.__members__.values()
            else req.type
        ),
        source=TaskSource.CHAT,
        title=req.title,
        description=req.description,
        repo=req.repo,
        source_id=req.source_id,
    )
    await store.save(task)

    ts = _thread_store(request)
    if ts is not None and req.origin_thread_id:
        try:
            await ts.link_task(
                thread_id=req.origin_thread_id,
                task_id=task.id,
                relation="origin",
            )
        except ValueError:
            # Bad relation is impossible here (hardcoded), but sqlite FK failure
            # could occur if thread_id is bogus — surface loudly.
            raise HTTPException(
                status_code=400,
                detail=f"origin_thread_id does not exist: {req.origin_thread_id}",
            )

    return await _task_dict(task, ts)


@router.get("/{task_id}")
async def get_task(task_id: str, request: Request):
    store = get_store()
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    ts = _thread_store(request)
    payload = await _task_dict(task, ts)
    if ts is not None:
        payload["referenced_by_thread_ids"] = await ts.referencing_threads(task.id)
    return payload


@router.get("")
async def list_tasks(
    request: Request,
    status: str | None = None,
    type: str | None = None,
    origin_thread_id: str | None = None,
):
    store = get_store()
    if status:
        tasks = await store.list_by_status(TaskStatus(status))
    else:
        tasks = await store.list_all()
    if type:
        tasks = [t for t in tasks if t.type == type]

    ts = _thread_store(request)
    # Thread-scoped filter: drop tasks whose origin thread isn't the requested
    # one. Runs after the in-memory list is built — small enough not to matter,
    # and avoids growing the store surface for a rarely-used query.
    if origin_thread_id and ts is not None:
        filtered: list = []
        for t in tasks:
            origin = await ts.origin_thread_for(t.id)
            if origin == origin_thread_id:
                filtered.append(t)
        tasks = filtered

    return [await _task_dict(t, ts) for t in tasks]
