"""Art session logs and agent check-ins.

Session logs are short markdown files the user (or the agent, on behalf of
the user) writes at ``Fields/Art/Session Log/YYYY-MM-DD <Title>.md`` after
each evening's practice. Check-ins are the agent's own reviews, written to
``Fields/Art/Check-ins/YYYY-MM-DD <Kind>.md`` — separated so the two
streams stay visually distinct in the vault.

The format mirrors the Workout Log convention: bold ``**Field:** value``
lines up top, then ## sections with the freeform content. Keeping the two
domain's notes structurally similar means the agent's mental model
transfers between them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from forge.notebook.errors import NotebookWriteError
from forge.notebook.reader import NotebookReader
from forge.notebook.writer import NotebookWriter

SESSION_LOG_DIR = "Fields/Art/Session Log"
CHECK_IN_DIR = "Fields/Art/Check-ins"
# Common image suffixes we'll treat as adjacent references for a session.
_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".heic")

_FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*(.*)\.md$")
_BOLD_FIELD_RE = re.compile(r"^\*\*([\w ]+):\*\*\s*(.+?)\s*$", re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")


def _strip_wikilink(value: str) -> str:
    return _WIKILINK_RE.sub(lambda m: m.group(1), value).strip()


@dataclass
class SessionEntry:
    path: str  # relative to notebook root
    date: date
    title: str
    evening: str | None  # "A" | "B" | "C"
    phase: int | None
    week: int | None
    duration_minutes: int | None
    materials: str | None
    focus: str | None
    images: list[str]  # relative paths to adjacent images, same date prefix
    raw: str

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "date": self.date.isoformat(),
            "title": self.title,
            "evening": self.evening,
            "phase": self.phase,
            "week": self.week,
            "duration_minutes": self.duration_minutes,
            "materials": self.materials,
            "focus": self.focus,
            "images": self.images,
            "raw": self.raw,
        }


def parse_session_markdown(path: str, body: str, images: list[str] | None = None) -> SessionEntry:
    """Pull structured fields out of a session log.

    ``images`` is passed in by the caller after scanning the directory — the
    parser itself is pure and doesn't touch the filesystem.
    """
    fname = Path(path).name
    m = _FILENAME_RE.match(fname)
    if m is None:
        raise ValueError(f"Not a session log filename: {fname}")
    entry_date = date.fromisoformat(m.group(1))
    title = m.group(2).strip() or entry_date.isoformat()

    fields = {k.strip(): v.strip() for k, v in _BOLD_FIELD_RE.findall(body)}

    def _opt_int(key: str) -> int | None:
        raw = fields.get(key)
        if not raw:
            return None
        match = re.search(r"\d+", raw)
        return int(match.group()) if match else None

    evening = None
    raw_evening = fields.get("Evening")
    if raw_evening:
        m2 = re.match(r"^([ABC])", raw_evening.strip(), re.IGNORECASE)
        if m2:
            evening = m2.group(1).upper()

    return SessionEntry(
        path=path,
        date=entry_date,
        title=title,
        evening=evening,
        phase=_opt_int("Phase"),
        week=_opt_int("Week"),
        duration_minutes=_opt_int("Duration"),
        materials=fields.get("Materials"),
        focus=fields.get("Focus") and _strip_wikilink(fields["Focus"]),
        images=list(images or []),
        raw=body,
    )


def render_session_template(
    *,
    entry_date: date,
    evening: str | None = None,
    phase: int | None = None,
    week: int | None = None,
    duration_minutes: int | None = None,
    materials: str | None = None,
    focus: str | None = None,
    body: str = "",
    reflection: str | None = None,
) -> str:
    """Render a new session log.

    Heading follows the Workout Log style (``# <weekday date>``) so the two
    logs read similarly.
    """
    weekday = entry_date.strftime("%a %d %B %Y")
    lines: list[str] = [f"# {weekday}", ""]
    if evening:
        lines.append(f"**Evening:** {evening}")
    if phase is not None:
        lines.append(f"**Phase:** {phase}")
    if week is not None:
        lines.append(f"**Week:** {week}")
    if duration_minutes is not None:
        lines.append(f"**Duration:** {duration_minutes} minutes")
    if materials:
        lines.append(f"**Materials:** {materials}")
    if focus:
        lines.append(f"**Focus:** {focus}")
    lines.append(f"**Daily Log:** [[{entry_date.isoformat()}]]")
    lines.append("")

    if body.strip():
        lines.append("## Session")
        lines.append("")
        lines.append(body.strip())
        lines.append("")

    if reflection and reflection.strip():
        lines.append("## Reflection")
        lines.append("")
        lines.append(reflection.strip())
        lines.append("")

    rendered = "\n".join(lines).rstrip() + "\n"
    return re.sub(r"\n{3,}", "\n\n", rendered)


def render_check_in_template(
    *,
    entry_date: date,
    kind: str,  # "weekly review" | "phase checkpoint" | "session critique" | ...
    phase: int | None = None,
    week: int | None = None,
    body: str = "",
) -> str:
    """Render a check-in note written by the agent.

    The caller is expected to supply ``body`` as already-formatted markdown.
    We prepend the metadata and heading so the vault page looks consistent.
    """
    weekday = entry_date.strftime("%a %d %B %Y")
    lines: list[str] = [f"# {weekday} — {kind.title()}", ""]
    if phase is not None:
        lines.append(f"**Phase:** {phase}")
    if week is not None:
        lines.append(f"**Week:** {week}")
    lines.append(f"**Kind:** {kind}")
    lines.append(f"**Daily Log:** [[{entry_date.isoformat()}]]")
    lines.append("")
    if body.strip():
        lines.append(body.strip())
        lines.append("")
    rendered = "\n".join(lines).rstrip() + "\n"
    return re.sub(r"\n{3,}", "\n\n", rendered)


class StudioSessions:
    """Filesystem helper for Session Log + Check-ins directories."""

    def __init__(self, reader: NotebookReader, writer: NotebookWriter):
        self._reader = reader
        self._writer = writer

    # ─── Sessions ──────────────────────────────────────────────────────

    def list_sessions(self, *, since: date | None = None) -> list[SessionEntry]:
        try:
            names = self._reader.list_dir(SESSION_LOG_DIR)
        except (FileNotFoundError, NotADirectoryError):
            return []
        entries: list[SessionEntry] = []
        names_set = set(names)
        for name in names:
            if not name.endswith(".md"):
                continue
            rel = f"{SESSION_LOG_DIR}/{name}"
            try:
                body = self._reader.read(rel)
            except (FileNotFoundError, ValueError):
                continue
            images = self._adjacent_images(name, names_set)
            try:
                entry = parse_session_markdown(rel, body, images=images)
            except ValueError:
                continue
            if since is not None and entry.date < since:
                continue
            entries.append(entry)
        entries.sort(key=lambda e: e.date, reverse=True)
        return entries

    def get_session(self, path: str) -> SessionEntry:
        body = self._reader.read(path)
        # Rescan the directory to discover adjacent images for this one file.
        fname = Path(path).name
        parent = Path(path).parent.as_posix() or SESSION_LOG_DIR
        try:
            siblings = set(self._reader.list_dir(parent))
        except (FileNotFoundError, NotADirectoryError):
            siblings = set()
        images = self._adjacent_images(fname, siblings, parent=parent)
        return parse_session_markdown(path, body, images=images)

    def create_session(
        self,
        *,
        entry_date: date,
        title: str,
        evening: str | None = None,
        phase: int | None = None,
        week: int | None = None,
        duration_minutes: int | None = None,
        materials: str | None = None,
        focus: str | None = None,
        body: str = "",
        reflection: str | None = None,
        overwrite: bool = False,
    ) -> str:
        safe_title = _safe_title(title)
        fname = f"{entry_date.isoformat()} {safe_title}.md"
        rel = f"{SESSION_LOG_DIR}/{fname}"
        if not overwrite and self._reader.exists(rel):
            raise NotebookWriteError(f"Session already exists at {rel}")
        content = render_session_template(
            entry_date=entry_date,
            evening=evening,
            phase=phase,
            week=week,
            duration_minutes=duration_minutes,
            materials=materials,
            focus=focus,
            body=body,
            reflection=reflection,
        )
        self._writer.write(rel, content)
        return rel

    # ─── Check-ins ─────────────────────────────────────────────────────

    def list_check_ins(self, *, since: date | None = None) -> list[dict]:
        try:
            names = self._reader.list_dir(CHECK_IN_DIR)
        except (FileNotFoundError, NotADirectoryError):
            return []
        out: list[dict] = []
        for name in names:
            if not name.endswith(".md"):
                continue
            rel = f"{CHECK_IN_DIR}/{name}"
            m = _FILENAME_RE.match(name)
            if not m:
                continue
            entry_date = date.fromisoformat(m.group(1))
            if since is not None and entry_date < since:
                continue
            try:
                body = self._reader.read(rel)
            except (FileNotFoundError, ValueError):
                continue
            out.append(
                {
                    "path": rel,
                    "date": entry_date.isoformat(),
                    "title": m.group(2).strip() or entry_date.isoformat(),
                    "preview": body[:400],
                }
            )
        out.sort(key=lambda e: e["date"], reverse=True)
        return out

    def create_check_in(
        self,
        *,
        entry_date: date,
        kind: str,
        phase: int | None,
        week: int | None,
        body: str,
        overwrite: bool = False,
    ) -> str:
        safe_kind = _safe_title(kind)
        fname = f"{entry_date.isoformat()} {safe_kind}.md"
        rel = f"{CHECK_IN_DIR}/{fname}"
        if not overwrite and self._reader.exists(rel):
            raise NotebookWriteError(f"Check-in already exists at {rel}")
        content = render_check_in_template(
            entry_date=entry_date,
            kind=kind,
            phase=phase,
            week=week,
            body=body,
        )
        self._writer.write(rel, content)
        return rel

    # ─── Helpers ───────────────────────────────────────────────────────

    def _adjacent_images(
        self, session_filename: str, siblings: set[str], parent: str = SESSION_LOG_DIR
    ) -> list[str]:
        """Return relative paths of image siblings that share the session's date prefix.

        The convention: a session note ``2026-04-14 Two-Value Studies.md`` pairs
        with any image file starting with ``2026-04-14`` in the same folder.
        """
        m = _FILENAME_RE.match(session_filename)
        if m is None:
            return []
        prefix = m.group(1)
        images: list[str] = []
        for name in siblings:
            if not name.startswith(prefix):
                continue
            lower = name.lower()
            if not any(lower.endswith(suffix) for suffix in _IMAGE_SUFFIXES):
                continue
            images.append(f"{parent}/{name}")
        images.sort()
        return images


def _safe_title(title: str) -> str:
    safe = title.strip()
    if not safe:
        raise ValueError("title must be non-empty")
    return re.sub(r"[/\\:\*\?\"<>\|]", "", safe).strip()
