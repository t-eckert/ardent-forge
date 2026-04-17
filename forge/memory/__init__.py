"""Forge memory — small markdown files Forge writes when it learns something stable.

The store is a plain directory of markdown files plus a top-level MEMORY.md
that indexes them. Matches the Claude Code memory format — one file per
memory, YAML-frontmatter header (name, description, type), markdown body.

Layers recap (orchestrator spec § Memory):
  1. Forge memory (THIS MODULE) — what Forge learned about the user
  2. Notebook                    — what the user wrote; read-only to Forge
  3. Thread history              — episodic, retrieval-only

Storage lives on the box at /data/ardent-forge/memory/. Not git-tracked;
backed up alongside the task DB.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

logger = logging.getLogger(__name__)

MemoryType = Literal["user", "feedback", "project", "reference"]
VALID_TYPES: tuple[MemoryType, ...] = ("user", "feedback", "project", "reference")

INDEX_FILENAME = "MEMORY.md"
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class MemoryEntry:
    """A single memory file.

    `filename` is the basename in the memory directory (e.g. "user_role.md").
    `name`, `description`, `type` come from YAML frontmatter.
    `body` is the markdown after the frontmatter.
    """

    filename: str
    name: str
    description: str
    type: MemoryType
    body: str
    updated_at: str | None = None

    @property
    def slug(self) -> str:
        return self.filename.removesuffix(".md")

    def to_markdown(self) -> str:
        parts = [
            "---",
            f"name: {self.name}",
            f"description: {self.description}",
            f"type: {self.type}",
        ]
        if self.updated_at:
            parts.append(f"updated: {self.updated_at}")
        parts.append("---")
        parts.append("")
        parts.append(self.body.rstrip() + "\n")
        return "\n".join(parts)


def _slugify(name: str) -> str:
    s = _SLUG_RE.sub("_", name.lower()).strip("_")
    return s or "memory"


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    header_lines, body = m.group(1), m.group(2)
    headers: dict[str, str] = {}
    for line in header_lines.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        headers[k.strip()] = v.strip()
    return headers, body


def _now() -> str:
    return datetime.now(timezone.utc).date().isoformat()


class MemoryStore:
    """Filesystem-backed memory store.

    Does not cache — every read touches disk. The whole store is small enough
    (dozens of files, tens of KB each) that re-reading is cheaper than keeping
    state in sync with user edits.
    """

    def __init__(self, root: str | Path):
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def read_index(self) -> str:
        """Return MEMORY.md contents. Empty string if the index doesn't exist."""
        path = self._root / INDEX_FILENAME
        if not path.is_file():
            return ""
        return path.read_text()

    def list(self) -> list[MemoryEntry]:
        """All memory entries, sorted by filename."""
        entries: list[MemoryEntry] = []
        for path in sorted(self._root.glob("*.md")):
            if path.name == INDEX_FILENAME:
                continue
            entry = self._read_entry(path)
            if entry is not None:
                entries.append(entry)
        return entries

    def get(self, filename: str) -> MemoryEntry | None:
        path = self._entry_path(filename)
        if not path.is_file():
            return None
        return self._read_entry(path)

    def write(
        self,
        *,
        name: str,
        description: str,
        type: MemoryType,
        body: str,
        filename: str | None = None,
    ) -> MemoryEntry:
        """Create or overwrite a memory. Regenerates MEMORY.md afterwards."""
        if type not in VALID_TYPES:
            raise ValueError(f"Unknown memory type: {type!r}")
        fname = filename or f"{_slugify(name)}.md"
        if not fname.endswith(".md"):
            fname += ".md"
        entry = MemoryEntry(
            filename=fname,
            name=name,
            description=description,
            type=type,
            body=body,
            updated_at=_now(),
        )
        self._entry_path(fname).write_text(entry.to_markdown())
        self._regenerate_index()
        try:
            from forge.metrics import MEMORY_WRITES_TOTAL
            MEMORY_WRITES_TOTAL.labels(type=type).inc()
        except Exception:
            pass  # Metrics are best-effort; never block a memory write.
        return entry

    def remove(self, filename: str) -> bool:
        """Delete a memory file. Returns True if it existed."""
        path = self._entry_path(filename)
        if not path.is_file():
            return False
        path.unlink()
        self._regenerate_index()
        return True

    # ─── internals ─────────────────────────────────────────────────────────

    def _entry_path(self, filename: str) -> Path:
        if not filename.endswith(".md"):
            filename += ".md"
        # Refuse traversal outside the store.
        path = (self._root / filename).resolve()
        if not path.is_relative_to(self._root.resolve()):
            raise ValueError(f"Invalid memory filename: {filename!r}")
        return path

    def _read_entry(self, path: Path) -> MemoryEntry | None:
        try:
            text = path.read_text()
        except OSError:
            logger.exception("Failed to read memory file %s", path)
            return None
        headers, body = _parse_frontmatter(text)
        mem_type = headers.get("type", "")
        if mem_type not in VALID_TYPES:
            logger.warning("Memory %s has missing/invalid type %r; skipping", path.name, mem_type)
            return None
        return MemoryEntry(
            filename=path.name,
            name=headers.get("name", path.stem),
            description=headers.get("description", ""),
            type=mem_type,  # type: ignore[arg-type]
            body=body.strip() + "\n",
            updated_at=headers.get("updated"),
        )

    def _regenerate_index(self) -> None:
        """Rewrite MEMORY.md as a flat list of entries.

        Format: `- [Name](filename.md) — description` per line, grouped by type.
        Kept short so it's cheap to preload into every system prompt.
        """
        entries = self.list()
        if not entries:
            (self._root / INDEX_FILENAME).write_text("")
            return
        by_type: dict[str, list[MemoryEntry]] = {}
        for e in entries:
            by_type.setdefault(e.type, []).append(e)
        lines: list[str] = []
        for t in VALID_TYPES:
            bucket = by_type.get(t, [])
            if not bucket:
                continue
            lines.append(f"## {t}")
            for e in bucket:
                lines.append(f"- [{e.name}]({e.filename}) — {e.description}")
            lines.append("")
        (self._root / INDEX_FILENAME).write_text("\n".join(lines).rstrip() + "\n")


__all__ = ["MemoryEntry", "MemoryStore", "MemoryType", "VALID_TYPES", "INDEX_FILENAME"]
