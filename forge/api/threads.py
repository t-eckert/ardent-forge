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


def _message_dict(m) -> dict:
    return {
        "id": m.id,
        "thread_id": m.thread_id,
        "role": m.role,
        "content": m.content,
        "variant": m.variant,
        "widgets": m.widgets,
        "task_id": m.task_id,
        "created_at": m.created_at,
    }


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
    return {**_thread_dict(t), "messages": [_message_dict(m) for m in msgs]}


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
