"""/api/threads — CRUD over conversations + tasks linked to threads.

Backed by ThreadStore (forge/thread_store.py). Exposes the primitives the
UI needs to render Threads spine + thread detail + the assistant-message
variants (text / widget / task-dispatched / task-resolved / memory-saved).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from forge.thread_store import Relation, ThreadStore, Variant

router = APIRouter(prefix="/api/threads")


# Status → current_stage mapping. An executing task is "inside" the execute
# stage; completed/failed have no active stage (the UI renders the final
# status chip instead).
_STATUS_TO_STAGE: dict[str, str | None] = {
    "queued": "triage",
    "triaging": "triage",
    "executing": "execute",
    "verifying": "verify",
    "delivering": "deliver",
    "completed": None,
    "failed": None,
}


def _store(request: Request) -> ThreadStore:
    store = getattr(request.app.state, "thread_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Thread store not configured")
    return store


def _thread_dict(t) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "kind": t.kind,
        "last_activity_at": t.last_activity_at,
        "unread": t.unread,
        "created_at": t.created_at,
    }


def _task_summary_dict(task, agent_stages: list[str] | None) -> dict:
    """Compact task shape embedded into task-dispatched / task-resolved messages.

    handler_data is intentionally omitted — large and not needed by the UI
    today. result rides along only for completed tasks so the resolved-
    message widget has something to render.
    """
    status = task.status.value if hasattr(task.status, "value") else str(task.status)
    return {
        "id": task.id,
        "type": str(task.type),
        "title": task.title,
        "status": status,
        "stages": agent_stages or [],
        "current_stage": _STATUS_TO_STAGE.get(status),
        "result": task.result if status == "completed" else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def _message_dict(m) -> dict:
    return {
        "id": m.id,
        "thread_id": m.thread_id,
        "role": m.role,
        "content": m.content,
        "variant": m.variant,
        "widgets": m.widgets,
        "task_id": m.task_id,
        "tool_use_id": getattr(m, "tool_use_id", None),
        "created_at": m.created_at,
    }


async def _enrich_with_tasks(messages: list[dict], request: Request) -> list[dict]:
    """For every task-variant message, fetch its Task and embed a summary.

    Unknown / deleted task_ids get ``task: None`` so the UI can fall back to
    the stored narration without exploding.
    """
    # TaskStore is held as a module-level singleton on forge.api.tasks rather
    # than on app.state; reach it through the existing accessor.
    from forge.api.tasks import _store as task_store_ref

    task_store = task_store_ref
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if task_store is None:
        return messages

    needs_enrichment = [
        m for m in messages
        if m["variant"] in ("task-dispatched", "task-resolved") and m["task_id"]
    ]
    if not needs_enrichment:
        return messages

    # One round-trip per unique task_id — threads rarely have more than a
    # handful of task-variant messages, so a pre-existing TaskStore.get
    # loop is fine. Revisit with a batch query if a real thread grows deep.
    unique_ids = {m["task_id"] for m in needs_enrichment}
    tasks = {}
    for tid in unique_ids:
        tasks[tid] = await task_store.get(tid)

    for m in needs_enrichment:
        task = tasks.get(m["task_id"])
        if task is None:
            m["task"] = None
            continue
        stages = None
        if orchestrator is not None and orchestrator.agents is not None:
            agent = orchestrator.agents.get(str(task.type))
            if agent is not None:
                stages = list(agent.stages)
        m["task"] = _task_summary_dict(task, stages)

    return messages


# ─── Thread CRUD ────────────────────────────────────────────────────────────


class ThreadCreate(BaseModel):
    title: str
    kind: str = "chat"
    thread_id: str | None = Field(default=None, description="Supply to use a specific id")


@router.get("")
async def list_threads(request: Request, limit: int = 100):
    return [_thread_dict(t) for t in await _store(request).list(limit=limit)]


@router.post("")
async def create_thread(body: ThreadCreate, request: Request):
    t = await _store(request).create(
        title=body.title, kind=body.kind, thread_id=body.thread_id
    )
    return _thread_dict(t)


@router.get("/{thread_id}")
async def get_thread(thread_id: str, request: Request):
    store = _store(request)
    t = await store.get(thread_id)
    if t is None:
        raise HTTPException(status_code=404, detail=f"No thread: {thread_id}")
    msgs = await store.list_messages(thread_id)
    message_dicts = [_message_dict(m) for m in msgs]
    await _enrich_with_tasks(message_dicts, request)
    return {**_thread_dict(t), "messages": message_dicts}


# ─── Messages ───────────────────────────────────────────────────────────────


class MessageCreate(BaseModel):
    role: str  # 'user' | 'assistant'
    content: str
    variant: Variant = "text"
    widgets: list[dict[str, Any]] = Field(default_factory=list)
    task_id: str | None = None


@router.post("/{thread_id}/messages")
async def append_message(thread_id: str, body: MessageCreate, request: Request):
    store = _store(request)
    # Ensure the thread exists; better 404 than a FK violation buried in SQLite.
    if await store.get(thread_id) is None:
        raise HTTPException(status_code=404, detail=f"No thread: {thread_id}")
    m = await store.append_message(
        thread_id=thread_id,
        role=body.role,
        content=body.content,
        variant=body.variant,
        widgets=body.widgets,
        task_id=body.task_id,
    )
    # User-authored posts flag the thread unread for the author-opposite side;
    # for this single-user system it primarily drives the sidebar indicator.
    await store.mark_activity(thread_id, unread=(body.role == "assistant"))
    return _message_dict(m)


# ─── Task ↔ Thread join ─────────────────────────────────────────────────────


class LinkRequest(BaseModel):
    task_id: str
    relation: Relation = "origin"


@router.post("/{thread_id}/tasks")
async def link_task(thread_id: str, body: LinkRequest, request: Request):
    store = _store(request)
    if await store.get(thread_id) is None:
        raise HTTPException(status_code=404, detail=f"No thread: {thread_id}")
    try:
        await store.link_task(
            thread_id=thread_id, task_id=body.task_id, relation=body.relation
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"thread_id": thread_id, "task_id": body.task_id, "relation": body.relation}


@router.get("/{thread_id}/tasks")
async def tasks_for_thread(thread_id: str, request: Request):
    return await _store(request).tasks_for_thread(thread_id)
