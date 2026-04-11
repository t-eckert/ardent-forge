from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
    name: str
    cron_expr: str
    task_type: str
    task_template: dict | None = None


class UpdateScheduleRequest(BaseModel):
    enabled: bool


@router.get("")
async def list_schedules():
    store = get_store()
    return await store.list_schedules()


@router.post("", status_code=201)
async def create_schedule(req: CreateScheduleRequest):
    store = get_store()
    schedule_id = await store.save_schedule(
        name=req.name,
        cron_expr=req.cron_expr,
        task_type=req.task_type,
        task_template=req.task_template,
    )
    schedule = await store.get_schedule(schedule_id)
    return schedule


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: str):
    store = get_store()
    existing = await store.get_schedule(schedule_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await store.delete_schedule(schedule_id)
    return {"status": "deleted"}


@router.patch("/{schedule_id}")
async def update_schedule(schedule_id: str, req: UpdateScheduleRequest):
    store = get_store()
    existing = await store.get_schedule(schedule_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await store.update_schedule_enabled(schedule_id, req.enabled)
    return await store.get_schedule(schedule_id)
