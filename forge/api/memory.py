"""/api/memory — CRUD over Forge memory entries.

Surfaces the MemoryStore to the UI's Library/Memory view (and any human
who wants to curate what Forge remembers). Read paths return the parsed
MemoryEntry; write/patch accept JSON.

Writes regenerate MEMORY.md automatically; subsequent chat turns pick up
the new index via the orchestrator's system prompt builder.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from forge.memory import MemoryStore, MemoryType, VALID_TYPES

router = APIRouter(prefix="/api/memory")


def _store(request: Request) -> MemoryStore:
    store = getattr(request.app.state, "memory_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Memory store not configured")
    return store


def _to_dict(entry) -> dict:
    return {
        "filename": entry.filename,
        "slug": entry.slug,
        "name": entry.name,
        "description": entry.description,
        "type": entry.type,
        "body": entry.body,
        "updated_at": entry.updated_at,
    }


class MemoryWrite(BaseModel):
    name: str
    description: str
    type: MemoryType = Field(..., description="One of: " + ", ".join(VALID_TYPES))
    body: str
    filename: str | None = None


@router.get("")
async def list_memory(request: Request):
    store = _store(request)
    return [_to_dict(e) for e in store.list()]


@router.get("/index", response_class=None)
async def get_index(request: Request) -> dict:
    """The raw MEMORY.md contents — what gets preloaded into Forge's system prompt."""
    return {"index": _store(request).read_index()}


@router.get("/{filename}")
async def get_memory(filename: str, request: Request):
    entry = _store(request).get(filename)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No memory: {filename}")
    return _to_dict(entry)


@router.post("")
@router.put("/{filename}")
async def write_memory(body: MemoryWrite, request: Request, filename: str | None = None):
    store = _store(request)
    entry = store.write(
        name=body.name,
        description=body.description,
        type=body.type,
        body=body.body,
        filename=filename or body.filename,
    )
    return _to_dict(entry)


@router.delete("/{filename}")
async def delete_memory(filename: str, request: Request):
    ok = _store(request).remove(filename)
    if not ok:
        raise HTTPException(status_code=404, detail=f"No memory: {filename}")
    return {"deleted": filename}
