"""/api/notebook — read/write access to the Obsidian vault for the UI."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from forge.notebook.writer import VALID_CHECKBOX_MARKERS

router = APIRouter(prefix="/api/notebook")


def _reader(request: Request):
    reader = getattr(request.app.state, "notebook_reader", None)
    if reader is None:
        raise HTTPException(status_code=503, detail="Notebook reader not configured")
    return reader


@router.get("/read")
async def read_page(path: str, request: Request):
    """Read a single notebook page by vault-relative path.

    Examples:
      /api/notebook/read?path=Log/2026-04-13.md
      /api/notebook/read?path=Fields/Health/Workouts.md
    """
    reader = _reader(request)
    try:
        if not reader.exists(path):
            raise HTTPException(status_code=404, detail=f"Page not found: {path}")
        body = reader.read(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"path": path, "body": body}


@router.get("/list")
async def list_directory(request: Request, path: str = ""):
    """List entries under a vault-relative directory. Empty path = vault root."""
    reader = _reader(request)
    try:
        entries = reader.list_dir(path)
    except NotADirectoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"path": path, "entries": entries}


@router.get("/search")
async def search(request: Request, q: str = Query(max_length=1000), path: str | None = Query(default=None, max_length=500)):
    reader = _reader(request)
    hits = reader.search(q, path_prefix=path)
    return [
        {"path": h.path, "line_number": h.line_number, "line": h.line}
        for h in hits
    ]


@router.get("/counts")
async def counts(request: Request):
    """Count .md files in each top-level notebook directory."""
    reader = _reader(request)
    root = reader._root

    def _count(dirname: str) -> int:
        d = root / dirname
        if not d.is_dir():
            return 0
        return sum(1 for _ in d.rglob("*.md"))

    return {
        "log": _count("Log"),
        "wiki": _count("Wiki"),
        "fields": _count("Fields"),
        "people": _count("People"),
        "collections": _count("Collections"),
    }


@router.get("/resolve")
async def resolve_wikilink(name: str, request: Request):
    """Find the vault-relative path for an Obsidian wikilink name."""
    reader = _reader(request)
    resolved = reader.resolve_wikilink(name)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"No note matches: {name}")
    return {"name": name, "path": str(resolved)}


class CheckboxUpdate(BaseModel):
    path: str
    line: int
    marker: str


@router.patch("/checkbox")
async def update_checkbox(body: CheckboxUpdate, request: Request):
    """Update a task checkbox marker on a specific line of a notebook file."""
    writer = getattr(request.app.state, "notebook_writer", None)
    if writer is None:
        raise HTTPException(status_code=503, detail="Notebook writer not configured")
    if body.marker not in VALID_CHECKBOX_MARKERS:
        raise HTTPException(status_code=422, detail=f"Invalid marker: {body.marker!r}")
    try:
        writer.update_checkbox(body.path, body.line, body.marker)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"path": body.path, "line": body.line, "marker": body.marker}
