"""/api/todos — lightweight personal todo CRUD.

Todos are distinct from Tasks (agent work). They're personal items shown on
the Today surface: errands, reviews, rituals, health checkboxes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/todos")


def _db(request: Request):
    store = getattr(request.app.state, "coordinator", None)
    if store is not None:
        return store._store._db
    # Fallback for tests that attach db directly.
    return getattr(request.app.state, "db", None)


class TodoCreate(BaseModel):
    title: str = Field(max_length=500)
    status: str = Field(default="open", max_length=32)
    category: str = Field(default="work", max_length=64)
    context: str | None = Field(default=None, max_length=2000)
    due_iso: str | None = Field(default=None, max_length=32)


class TodoPatch(BaseModel):
    title: str | None = None
    status: str | None = None
    category: str | None = None
    context: str | None = None
    due_iso: str | None = None


@router.get("")
async def list_todos(request: Request, due: str | None = None):
    db = _db(request)
    if db is None:
        return []
    if due == "today":
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = await db.fetch_all(
            "SELECT * FROM todos WHERE due_iso LIKE ? OR due_iso IS NULL "
            "ORDER BY created_at ASC",
            (f"{today}%",),
        )
    else:
        rows = await db.fetch_all(
            "SELECT * FROM todos ORDER BY created_at ASC"
        )
    return [dict(r) for r in rows]


@router.post("")
async def create_todo(body: TodoCreate, request: Request):
    db = _db(request)
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    import ulid as _ulid

    todo_id = str(_ulid.new())
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO todos (id, title, status, category, context, due_iso, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (todo_id, body.title, body.status, body.category, body.context, body.due_iso, now),
    )
    return {
        "id": todo_id,
        "title": body.title,
        "status": body.status,
        "category": body.category,
        "context": body.context,
        "due_iso": body.due_iso,
        "created_at": now,
    }


@router.patch("/{todo_id}")
async def update_todo(todo_id: str, body: TodoPatch, request: Request):
    db = _db(request)
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    row = await db.fetch_one("SELECT * FROM todos WHERE id = ?", (todo_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return dict(row)
    _ALLOWED_COLUMNS = {"title", "status", "category", "context", "due_iso"}
    updates = {k: v for k, v in updates.items() if k in _ALLOWED_COLUMNS}
    if not updates:
        return dict(row)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [todo_id]
    await db.execute(f"UPDATE todos SET {set_clause} WHERE id = ?", tuple(values))
    updated = await db.fetch_one("SELECT * FROM todos WHERE id = ?", (todo_id,))
    return dict(updated)


@router.delete("/{todo_id}")
async def delete_todo(todo_id: str, request: Request):
    db = _db(request)
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    await db.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    return {"deleted": True}
