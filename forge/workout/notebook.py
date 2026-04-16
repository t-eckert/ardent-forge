"""Workout notebook access — parse log entries, read equipment definitions,
write new workout templates into Fields/Health/Workout Log/.

The notebook stores workouts as ``Fields/Health/Workout Log/YYYY-MM-DD <title>.md``.
The format is hand-written markdown with bold field lines (``**Duration:** 45 minutes``)
and Obsidian wikilinks for locations. We parse what's reliably structured and
hand the raw body back alongside it so the agent can fill in gaps.

Equipment definitions live at ``Fields/Health/<Gym Name>.md`` and have an
"Equipment Available" section followed by "Exercises by Equipment" tables.
We surface both the friendly summary and the raw note.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from forge.notebook.errors import NotebookWriteError
from forge.notebook.reader import NotebookReader
from forge.notebook.writer import NotebookWriter

# All workout logs live under this path (relative to notebook root).
WORKOUT_LOG_DIR = "Fields/Health/Workout Log"
# Known equipment/location notes. Paths are relative to the notebook root.
# New locations: add the note and register it here.
KNOWN_LOCATIONS: dict[str, str] = {
    "Fire Hall Gym": "Fields/Health/Fire Hall Gym.md",
    "Home": "Fields/Health/Home Gym Equipment.md",
}

_FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*(.*)\.md$")
_BOLD_FIELD_RE = re.compile(r"^\*\*([\w ]+):\*\*\s*(.+?)\s*$", re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")
_DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(min|mins|minutes|hr|hrs|hours)", re.IGNORECASE)


def _strip_wikilink(value: str) -> str:
    """Turn ``[[Fire Hall Gym]]`` into ``Fire Hall Gym``. Preserves plain text."""
    return _WIKILINK_RE.sub(lambda m: m.group(1), value).strip()


@dataclass
class WorkoutEntry:
    """Parsed view of a single notebook workout log.

    Structured fields are best-effort — the ``raw`` body is always present so
    the caller can recover anything the parser missed.
    """

    path: str  # relative to notebook root
    date: date
    title: str  # derived from filename, e.g. "Upper Body"
    duration_minutes: int | None
    program: str | None
    location: str | None
    raw: str

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "date": self.date.isoformat(),
            "title": self.title,
            "duration_minutes": self.duration_minutes,
            "program": self.program,
            "location": self.location,
            "raw": self.raw,
        }


@dataclass
class EquipmentLocation:
    """Equipment available at a named training location.

    ``equipment`` is the flat list parsed from the "Equipment Available"
    section; ``exercises_by_equipment`` maps each heading under "Exercises
    by Equipment" to its table rows. ``raw`` is the full note body so the
    agent can read notes the parser didn't surface (hours, rules, etc.).
    """

    name: str
    path: str
    equipment: list[str] = field(default_factory=list)
    exercises_by_equipment: dict[str, list[str]] = field(default_factory=dict)
    raw: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "equipment": self.equipment,
            "exercises_by_equipment": self.exercises_by_equipment,
            "raw": self.raw,
        }


def parse_workout_markdown(path: str, body: str) -> WorkoutEntry:
    """Extract structured fields from a workout log note.

    ``path`` is the relative path (used for the filename date + title fallback).
    """
    fname = Path(path).name
    m = _FILENAME_RE.match(fname)
    if m is None:
        raise ValueError(f"Not a workout log filename: {fname}")
    entry_date = date.fromisoformat(m.group(1))
    title_from_filename = m.group(2).strip() or entry_date.isoformat()

    fields = {key.strip(): value.strip() for key, value in _BOLD_FIELD_RE.findall(body)}

    duration_minutes: int | None = None
    raw_duration = fields.get("Duration")
    if raw_duration:
        dm = _DURATION_RE.search(raw_duration)
        if dm:
            value = float(dm.group(1))
            unit = dm.group(2).lower()
            if unit.startswith("hr") or unit.startswith("hour"):
                duration_minutes = int(value * 60)
            else:
                duration_minutes = int(value)

    program = fields.get("Program")
    location_raw = fields.get("Location")
    location = _strip_wikilink(location_raw) if location_raw else None

    return WorkoutEntry(
        path=path,
        date=entry_date,
        title=title_from_filename,
        duration_minutes=duration_minutes,
        program=program,
        location=location,
        raw=body,
    )


def parse_equipment_markdown(name: str, path: str, body: str) -> EquipmentLocation:
    """Extract the equipment summary + per-equipment exercise tables.

    Looks for an "Equipment Available" section (bulleted list) and an
    "Exercises by Equipment" section (sub-headings → markdown tables).
    Sections are identified by ``## `` headings in the source.
    """
    equipment = _extract_equipment_list(body)
    exercises = _extract_exercises_by_equipment(body)
    return EquipmentLocation(
        name=name,
        path=path,
        equipment=equipment,
        exercises_by_equipment=exercises,
        raw=body,
    )


def _iter_sections(body: str, level: int = 2) -> list[tuple[str, str]]:
    """Split markdown body on heading of the given level.

    Returns ``[(heading_text, section_body), ...]``. The body of each section
    is everything up to the next heading of the same level. Anything before
    the first matching heading is discarded.
    """
    pattern = re.compile(rf"^{'#' * level} +(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(body))
    out: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out.append((heading, body[start:end].strip()))
    return out


def _extract_equipment_list(body: str) -> list[str]:
    """Collect bullet points under "Equipment Available" across sub-categories.

    The section mixes sub-headings (``**Cardio Equipment:**``) and bullets —
    we keep the sub-heading as context by prefixing bullet items with it when
    present. Keeps ordering stable.
    """
    items: list[str] = []
    current_category: str | None = None
    found = False
    for heading, section in _iter_sections(body, level=2):
        if not heading.lower().startswith("equipment"):
            continue
        found = True
        for line in section.splitlines():
            stripped = line.strip()
            if not stripped:
                current_category = None
                continue
            cat_match = re.match(r"^\*\*(.+?):?\*\*:?\s*$", stripped)
            if cat_match:
                current_category = cat_match.group(1).strip().rstrip(":")
                continue
            if stripped.startswith(("- ", "* ")):
                item = stripped[2:].strip()
                if current_category:
                    items.append(f"{current_category}: {item}")
                else:
                    items.append(item)
        break
    if not found:
        return []
    return items


def _extract_exercises_by_equipment(body: str) -> dict[str, list[str]]:
    """Walk the "Exercises by Equipment" section and flatten each sub-section
    into a list of human-readable "category — exercises" strings.
    """
    out: dict[str, list[str]] = {}
    target_section: str | None = None
    for heading, section in _iter_sections(body, level=2):
        if heading.lower().startswith("exercises by equipment"):
            target_section = section
            break
    if target_section is None:
        return out

    # Each sub-section is introduced by a ### heading.
    for sub_heading, sub_body in _iter_sections(target_section, level=3):
        rows: list[str] = []
        for line in sub_body.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            # Skip the header row and the separator row (| --- | --- |).
            if set(stripped.replace("|", "").strip()) <= set("-: "):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) < 2:
                continue
            if cells[0].lower() in ("muscle group", "exercise type", "category", "equipment"):
                continue
            rows.append(f"{cells[0]} — {cells[1]}")
        if rows:
            out[sub_heading] = rows
    return out


def render_workout_template(
    *,
    entry_date: date,
    location: str | None,
    duration_minutes: int | None,
    program: str | None,
    sections: list[tuple[str, str]] | None = None,
    extra_metadata: dict[str, str] | None = None,
    notes: str | None = None,
) -> str:
    """Render a new workout log file body.

    ``sections`` is a list of ``(heading, body)`` pairs for the main workout
    body (warm-up, strength training, cool-down, etc.). The caller — usually
    the agent composing from equipment — decides what goes in each. Location
    is wrapped as a wikilink so it links to the gym note in Obsidian.

    Note: the title lives in the filename (``YYYY-MM-DD <title>.md``). Existing
    entries use the weekday date as the body heading, not the title, so that's
    what we render here for consistency.
    """
    weekday = entry_date.strftime("%a %d %B %Y")
    lines: list[str] = [f"# {weekday}", ""]
    if duration_minutes is not None:
        lines.append(f"**Duration:** {duration_minutes} minutes")
    if program:
        lines.append(f"**Program:** {program}")
    if location:
        lines.append(f"**Location:** [[{location}]]")
    lines.append(f"**Daily Log:** [[{entry_date.isoformat()}]]")
    if extra_metadata:
        for key, value in extra_metadata.items():
            lines.append(f"**{key}:** {value}")
    lines.append("")

    for heading, content in sections or []:
        lines.append(f"## {heading}")
        lines.append("")
        lines.append(content.strip())
        lines.append("")

    if notes:
        lines.append("## Notes")
        lines.append("")
        lines.append(notes.strip())
        lines.append("")

    body = "\n".join(lines).rstrip() + "\n"
    # Collapse runs of >2 blank lines that can creep in from empty section bodies.
    return re.sub(r"\n{3,}", "\n\n", body)


class NotebookWorkouts:
    """Read/write helper for workout logs and equipment notes.

    Sync by design — filesystem operations are fast enough that we don't need
    an async wrapper at this layer. The connector offloads to ``asyncio.to_thread``
    when it surfaces these methods as tools.
    """

    def __init__(self, reader: NotebookReader, writer: NotebookWriter):
        self._reader = reader
        self._writer = writer

    # ─── Reading workouts ──────────────────────────────────────────────

    def list_entries(self, *, since: date | None = None) -> list[WorkoutEntry]:
        """Return every parseable workout log entry, newest first.

        Entries with unparseable filenames (missing date) are skipped silently —
        the log dir also gets stray notes and we don't want one bad file to
        bring the whole list down.
        """
        try:
            names = self._reader.list_dir(WORKOUT_LOG_DIR)
        except (FileNotFoundError, NotADirectoryError):
            return []

        entries: list[WorkoutEntry] = []
        for name in names:
            if not name.endswith(".md"):
                continue
            rel = f"{WORKOUT_LOG_DIR}/{name}"
            try:
                body = self._reader.read(rel)
                entry = parse_workout_markdown(rel, body)
            except (ValueError, FileNotFoundError):
                continue
            if since is not None and entry.date < since:
                continue
            entries.append(entry)
        entries.sort(key=lambda e: e.date, reverse=True)
        return entries

    def get_entry(self, path: str) -> WorkoutEntry:
        """Fetch a single workout log by relative path."""
        body = self._reader.read(path)
        return parse_workout_markdown(path, body)

    # ─── Locations and equipment ───────────────────────────────────────

    def list_locations(self) -> list[EquipmentLocation]:
        """Return every known training location's equipment summary."""
        out: list[EquipmentLocation] = []
        for name, path in KNOWN_LOCATIONS.items():
            try:
                body = self._reader.read(path)
            except (FileNotFoundError, ValueError):
                continue
            out.append(parse_equipment_markdown(name, path, body))
        return out

    def get_location(self, name: str) -> EquipmentLocation | None:
        """Return one location by name. Case-insensitive match."""
        key = name.strip().lower()
        for loc_name, path in KNOWN_LOCATIONS.items():
            if loc_name.lower() == key:
                try:
                    body = self._reader.read(path)
                except (FileNotFoundError, ValueError):
                    return None
                return parse_equipment_markdown(loc_name, path, body)
        return None

    # ─── Writing new workouts ──────────────────────────────────────────

    def create_entry(
        self,
        *,
        entry_date: date,
        title: str,
        location: str | None = None,
        duration_minutes: int | None = None,
        program: str | None = None,
        sections: list[tuple[str, str]] | None = None,
        notes: str | None = None,
        overwrite: bool = False,
    ) -> str:
        """Write a new workout log file. Returns the relative path written.

        Filename follows the existing convention ``YYYY-MM-DD <Title>.md``.
        Refuses to overwrite by default — the agent should pick a unique title
        (e.g. "Upper Body" and "Upper Body PM") rather than clobber history.
        """
        safe_title = title.strip()
        if not safe_title:
            raise ValueError("title must be non-empty")
        # Strip characters that don't belong in filenames. Keep spaces — they
        # match the existing naming style.
        safe_title = re.sub(r"[/\\:\*\?\"<>\|]", "", safe_title).strip()
        fname = f"{entry_date.isoformat()} {safe_title}.md"
        rel = f"{WORKOUT_LOG_DIR}/{fname}"
        if not overwrite and self._reader.exists(rel):
            raise NotebookWriteError(f"Workout already exists at {rel}")
        body = render_workout_template(
            entry_date=entry_date,
            location=location,
            duration_minutes=duration_minutes,
            program=program,
            sections=sections,
            notes=notes,
        )
        self._writer.write(rel, body)
        return rel
