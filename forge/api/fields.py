"""/api/fields — Library/Fields roster.

A Field is a life-area directory under Fields/ in the Notebook vault. This
endpoint enumerates them so the UI's Library/Fields index can render the
real grid instead of mocks.

Each field directory may contain an ``_meta.md`` file with YAML frontmatter
describing the field (category, tagline, status, sources). When present, the
frontmatter is merged into the API response so the UI can render real
metadata instead of mock data.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/fields")
logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _reader(request: Request):
    return getattr(request.app.state, "notebook_reader", None)


def _slug(name: str) -> str:
    s = _SLUG_RE.sub("-", name.lower()).strip("-")
    return s or name.lower()


def _parse_meta(meta_path: Path) -> dict:
    """Extract YAML frontmatter from a field's _meta.md file."""
    if not meta_path.is_file():
        return {}
    try:
        text = meta_path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return {}
        end = text.index("---", 3)
        return yaml.safe_load(text[3:end]) or {}
    except Exception:
        logger.debug("Could not parse frontmatter in %s", meta_path)
        return {}


def _scan_fields(root: Path) -> list[dict]:
    """Walk Fields/ directory → list of field summaries.

    Each child of Fields/ that's itself a directory is treated as a Field.
    Enriched with frontmatter from _meta.md when present.
    """
    fields_dir = root / "Fields"
    if not fields_dir.is_dir():
        return []
    out: list[dict] = []
    for child in sorted(fields_dir.iterdir()):
        if not child.is_dir():
            continue
        entries = sum(1 for _ in child.rglob("*.md") if _.name != "_meta.md")
        field: dict = {
            "slug": _slug(child.name),
            "name": child.name,
            "path": f"Fields/{child.name}",
            "entries": entries,
        }
        meta = _parse_meta(child / "_meta.md")
        for key in ("category", "tagline", "sources", "featured"):
            if key in meta:
                field[key] = meta[key]
        if "status" in meta and isinstance(meta["status"], dict):
            field["status"] = meta["status"]
        out.append(field)
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


@router.get("/{slug}/entries")
async def list_field_entries(slug: str, request: Request):
    """List markdown entries under a field directory."""
    reader = _reader(request)
    if reader is None:
        raise HTTPException(status_code=503, detail="Notebook reader not configured")
    fields = _scan_fields(reader._root)  # type: ignore[attr-defined]
    field = next((f for f in fields if f["slug"] == slug), None)
    if field is None:
        raise HTTPException(status_code=404, detail=f"No field: {slug}")
    field_dir = reader._root / field["path"]  # type: ignore[attr-defined]
    entries = sorted(
        p.stem for p in field_dir.rglob("*.md") if p.name != "_meta.md"
    )
    return {"slug": slug, "entries": entries}
