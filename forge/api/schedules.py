from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from forge.store import TaskStore

router = APIRouter(prefix="/api/schedules")

_store: TaskStore | None = None


def set_store(store: TaskStore):
    global _store
    _store = store


def get_store() -> TaskStore:
    if _store is None:
        raise RuntimeError("Schedule store not configured")
    return _store


class CreateScheduleRequest(BaseModel):
    name: str = Field(max_length=200)
    cron_expr: str = Field(max_length=100)
    task_type: str = Field(max_length=64)
    # Code-task specifics
    repo: str | None = None          # GitHub owner/name
    prompt_template: str | None = None   # becomes task description on each fire
    label: str | None = None         # optional tag surfaced in task title
    # Fallback for custom task types
    task_template: dict | None = None


class UpdateScheduleRequest(BaseModel):
    enabled: bool


def _build_template(req: CreateScheduleRequest) -> dict:
    """Merge explicit fields and freeform task_template into one stored dict."""
    template = dict(req.task_template or {})
    if req.repo:
        template["repo"] = req.repo
    if req.prompt_template:
        template["description"] = req.prompt_template
    if req.label:
        template["label"] = req.label
    if req.prompt_template and not template.get("title"):
        # Derive a short title from the first line of the prompt
        template["title"] = req.prompt_template.splitlines()[0][:120]
    return template


@router.get("")
async def list_schedules():
    return await get_store().list_schedules()


@router.post("", status_code=201)
async def create_schedule(req: CreateScheduleRequest):
    store = get_store()
    template = _build_template(req)
    schedule_id = await store.save_schedule(
        name=req.name,
        cron_expr=req.cron_expr,
        task_type=req.task_type,
        task_template=template,
    )
    return await store.get_schedule(schedule_id)


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: str):
    store = get_store()
    if await store.get_schedule(schedule_id) is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await store.delete_schedule(schedule_id)
    return {"status": "deleted"}


@router.patch("/{schedule_id}")
async def update_schedule(schedule_id: str, req: UpdateScheduleRequest):
    store = get_store()
    if await store.get_schedule(schedule_id) is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await store.update_schedule_enabled(schedule_id, req.enabled)
    return await store.get_schedule(schedule_id)
