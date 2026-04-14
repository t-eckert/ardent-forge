"""/api/fields — Library/Fields roster.

A Field is a life-area directory under Fields/ in the Notebook vault. This
endpoint enumerates them so the UI's Library/Fields index can render the
real grid instead of mocks.

Per-field detail is intentionally thin here — the UI composes the full
Field view (workouts, PRs, readiness, etc) from multiple Forge endpoints
(notebook read + specialized connectors like health.workouts). This one
just lists what Fields exist and what metadata we can infer.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/fields")


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _reader(request: Request):
    return getattr(request.app.state, "notebook_reader", None)


def _slug(name: str) -> str:
    s = _SLUG_RE.sub("-", name.lower()).strip("-")
    return s or name.lower()


def _scan_fields(root: Path) -> list[dict]:
    """Walk Fields/ directory → list of field summaries.

    Each child of Fields/ that's itself a directory is treated as a Field.
    """
    fields_dir = root / "Fields"
    if not fields_dir.is_dir():
        return []
    out: list[dict] = []
    for child in sorted(fields_dir.iterdir()):
        if not child.is_dir():
            continue
        entries = sum(1 for _ in child.rglob("*.md"))
        out.append(
            {
                "slug": _slug(child.name),
                "name": child.name,
                "path": f"Fields/{child.name}",
                "entries": entries,
            }
        )
    return out


@router.get("")
async def list_fields(request: Request):
    reader = _reader(request)
    if reader is None:
        return []
    return _scan_fields(reader._root)  # type: ignore[attr-defined]


@router.get("/{slug}")
async def get_field(slug: str, request: Request):
    reader = _reader(request)
    if reader is None:
        raise HTTPException(status_code=503, detail="Notebook reader not configured")
    fields = _scan_fields(reader._root)  # type: ignore[attr-defined]
    for f in fields:
        if f["slug"] == slug:
            return f
    raise HTTPException(status_code=404, detail=f"No field: {slug}")
