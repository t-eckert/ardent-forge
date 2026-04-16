"""Parse ``Artistic Course of Study.md`` and resolve a date to the current focus.

The syllabus is hand-written markdown with a predictable shape:

  ## Phase N: <Name> (<Month>–<Month>)
  ### Core Concept
  <prose>
  ### Evening A Exercises
  **Weeks N–M: <Exercise name>.** <body>
  **Weeks X–Y: ...**
  ### Evening B Application
  ### Evening C Master Studies
  ### Phase N Checkpoint

We don't try to parse the prose — we extract the boundaries (phase headings,
week markers, sub-sections) so the connector and the agent prompt can pull
out exactly the relevant slice for any given date. Everything stays as raw
markdown so the agent sees the author's voice, not a lossy re-render.

Phase start dates are anchors supplied by the caller — the syllabus itself
only says "April–May" and similar, which isn't precise enough to compute
week-in-phase. ``PhaseSchedule`` binds concrete Monday-of-week-1 dates to
each phase number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta


# ─── Data model ────────────────────────────────────────────────────────


@dataclass
class WeekBlock:
    """One ``**Weeks N–M: Exercise name.** <body>`` line under Evening A."""

    first_week: int
    last_week: int  # inclusive
    title: str  # "Two-value studies"
    body: str  # everything after the bold lead-in, freeform

    def contains(self, week_in_phase: int) -> bool:
        return self.first_week <= week_in_phase <= self.last_week


@dataclass
class Phase:
    """One ``## Phase N: …`` section with its major sub-sections."""

    number: int
    title: str  # "Value Commitment"
    date_range_label: str  # "April–May" — presentation only
    core_concept: str
    evening_a_intro: str
    evening_a_weeks: list[WeekBlock]
    evening_b: str
    evening_c: str
    checkpoint: str

    def week_block_for(self, week_in_phase: int) -> WeekBlock | None:
        for wb in self.evening_a_weeks:
            if wb.contains(week_in_phase):
                return wb
        return None


@dataclass
class Syllabus:
    """The full parsed document."""

    title: str
    intro: str  # everything above the first ## Phase heading
    phases: list[Phase]
    ongoing_habits: str
    book_list: str
    medium_note: str
    raw: str

    def phase(self, number: int) -> Phase | None:
        for p in self.phases:
            if p.number == number:
                return p
        return None


# ─── Phase schedule (anchors date → phase/week) ────────────────────────


@dataclass
class PhaseSchedule:
    """Maps a calendar date to the phase/week-in-phase it falls in.

    The schedule is a list of (phase_number, start_date, duration_weeks)
    tuples in order. The last phase extends through its duration; dates
    beyond are reported as being in the last phase's final week.
    """

    anchors: list[tuple[int, date, int]]

    def resolve(self, today: date) -> tuple[int, int] | None:
        """Return (phase_number, week_in_phase) for ``today``, or None if before the start."""
        if not self.anchors:
            return None
        _, first_start, _ = self.anchors[0]
        if today < first_start:
            return None

        # Find the phase that contains today.
        for i, (phase_num, start, duration_weeks) in enumerate(self.anchors):
            next_start = (
                self.anchors[i + 1][1]
                if i + 1 < len(self.anchors)
                else start + timedelta(weeks=duration_weeks)
            )
            if start <= today < next_start:
                week = ((today - start).days // 7) + 1
                # Cap to the phase's declared duration so "overrun" weeks don't
                # report as week 47; clamp to the last week.
                week = min(week, duration_weeks)
                return phase_num, week

        # Past all phases — report last phase's last week.
        last_phase, _, last_duration = self.anchors[-1]
        return last_phase, last_duration


def default_phase_schedule(phase_1_start: date) -> PhaseSchedule:
    """The default durations implied by the syllabus.

    Phase 1 (April–May): 8 weeks
    Phase 2 (June–July): 8 weeks
    Phase 3 (August–October): 12 weeks
    """
    phase_2 = phase_1_start + timedelta(weeks=8)
    phase_3 = phase_2 + timedelta(weeks=8)
    return PhaseSchedule(
        anchors=[
            (1, phase_1_start, 8),
            (2, phase_2, 8),
            (3, phase_3, 12),
        ]
    )


# ─── Current focus resolver ────────────────────────────────────────────


@dataclass
class CurrentFocus:
    """A compact snapshot of "what should I be working on right now?"

    Structured for direct consumption by both the ``studio_current_focus``
    tool and the agent's prompt. Every field is stringy so the tool payload
    is trivially serialisable.
    """

    today: date
    phase_number: int
    phase_title: str
    phase_date_range: str
    week_in_phase: int
    evening_a_week_block: WeekBlock | None = None
    evening_b_body: str = ""
    evening_c_body: str = ""
    checkpoint: str = ""
    core_concept: str = ""

    @property
    def evening_a_title(self) -> str:
        return self.evening_a_week_block.title if self.evening_a_week_block else ""

    @property
    def evening_a_body(self) -> str:
        return self.evening_a_week_block.body if self.evening_a_week_block else ""

    def to_dict(self) -> dict:
        return {
            "today": self.today.isoformat(),
            "phase": {
                "number": self.phase_number,
                "title": self.phase_title,
                "date_range": self.phase_date_range,
            },
            "week_in_phase": self.week_in_phase,
            "evening_a": {
                "title": self.evening_a_title,
                "body": self.evening_a_body,
                "weeks": (
                    f"{self.evening_a_week_block.first_week}–"
                    f"{self.evening_a_week_block.last_week}"
                    if self.evening_a_week_block
                    else ""
                ),
            },
            "evening_b": self.evening_b_body,
            "evening_c": self.evening_c_body,
            "checkpoint": self.checkpoint,
            "core_concept": self.core_concept,
        }


def resolve_focus(
    syllabus: Syllabus,
    schedule: PhaseSchedule,
    today: date,
) -> CurrentFocus | None:
    """Resolve the syllabus slice that applies on ``today``.

    Returns ``None`` if ``today`` is before Phase 1's start — the syllabus
    hasn't begun yet. Otherwise clamps to the known phases.
    """
    resolved = schedule.resolve(today)
    if resolved is None:
        return None
    phase_num, week_in_phase = resolved
    phase = syllabus.phase(phase_num)
    if phase is None:
        return None
    return CurrentFocus(
        today=today,
        phase_number=phase.number,
        phase_title=phase.title,
        phase_date_range=phase.date_range_label,
        week_in_phase=week_in_phase,
        evening_a_week_block=phase.week_block_for(week_in_phase),
        evening_b_body=phase.evening_b,
        evening_c_body=phase.evening_c,
        checkpoint=phase.checkpoint,
        core_concept=phase.core_concept,
    )


# ─── Parser ────────────────────────────────────────────────────────────


_PHASE_HEADING_RE = re.compile(
    r"^##\s+Phase\s+(\d+)\s*:\s*(.+?)\s*\((.+?)\)\s*$", re.MULTILINE
)
_H3_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_WEEK_RE = re.compile(
    r"^\*\*Weeks?\s+(\d+)(?:[–-](\d+))?\s*:\s*(.+?)\*\*\s*(.*?)(?=^\*\*Weeks?\s+\d|\Z)",
    re.MULTILINE | re.DOTALL,
)


def parse_syllabus(body: str) -> Syllabus:
    """Parse the Course of Study markdown into a structured ``Syllabus``.

    Tolerant of small drift: missing sub-sections are returned as empty strings
    rather than raising. The intent is that the raw markdown remains the source
    of truth — this parser just makes it queryable.
    """
    title_match = re.match(r"^#\s+(.+?)\s*$", body, re.MULTILINE)
    title = title_match.group(1) if title_match else "Course of Study"

    phase_matches = list(_PHASE_HEADING_RE.finditer(body))
    intro_end = phase_matches[0].start() if phase_matches else len(body)
    intro = body[:intro_end].strip()

    phases: list[Phase] = []
    for i, match in enumerate(phase_matches):
        phase_num = int(match.group(1))
        phase_title = match.group(2).strip()
        phase_dates = match.group(3).strip()
        phase_start = match.end()
        phase_end = phase_matches[i + 1].start() if i + 1 < len(phase_matches) else None
        # Cap at the next top-level ## heading (e.g. "Ongoing Habits") if present.
        if phase_end is None:
            next_h2 = _H2_RE.search(body, phase_start)
            if next_h2 and not _PHASE_HEADING_RE.match(body, next_h2.start()):
                phase_end = next_h2.start()
        phase_body = body[phase_start : phase_end or len(body)]
        phases.append(_parse_phase(phase_num, phase_title, phase_dates, phase_body))

    # Post-phase sections: walk the remaining H2 headings.
    ongoing_habits = ""
    book_list = ""
    medium_note = ""
    post_start = (
        phase_matches[-1].end() if phase_matches else 0
    )
    remaining = body[post_start:]
    for heading, section_body in _iter_h2(remaining):
        lower = heading.lower()
        if "ongoing" in lower or "habit" in lower:
            ongoing_habits = section_body.strip()
        elif "book" in lower:
            book_list = section_body.strip()
        elif "medium" in lower:
            medium_note = section_body.strip()

    return Syllabus(
        title=title,
        intro=intro,
        phases=phases,
        ongoing_habits=ongoing_habits,
        book_list=book_list,
        medium_note=medium_note,
        raw=body,
    )


def _iter_h2(body: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    matches = list(_H2_RE.finditer(body))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out.append((m.group(1).strip(), body[start:end]))
    return out


@dataclass
class _PhaseSections:
    core_concept: str = ""
    evening_a: str = ""
    evening_b: str = ""
    evening_c: str = ""
    checkpoint: str = ""


def _parse_phase(
    number: int, title: str, date_label: str, phase_body: str
) -> Phase:
    sections = _split_phase_h3(phase_body)

    evening_a_intro, week_blocks = _parse_week_blocks(sections.evening_a)

    return Phase(
        number=number,
        title=title,
        date_range_label=date_label,
        core_concept=sections.core_concept,
        evening_a_intro=evening_a_intro,
        evening_a_weeks=week_blocks,
        evening_b=sections.evening_b,
        evening_c=sections.evening_c,
        checkpoint=sections.checkpoint,
    )


def _split_phase_h3(body: str) -> _PhaseSections:
    """Walk the ### sub-sections inside one phase."""
    out = _PhaseSections()
    matches = list(_H3_RE.finditer(body))
    for i, m in enumerate(matches):
        heading = m.group(1).strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section = body[start:end].strip()
        if "core concept" in heading:
            out.core_concept = section
        elif heading.startswith("evening a"):
            out.evening_a = section
        elif heading.startswith("evening b"):
            out.evening_b = section
        elif heading.startswith("evening c"):
            out.evening_c = section
        elif "checkpoint" in heading:
            out.checkpoint = section
    return out


def _parse_week_blocks(evening_a_body: str) -> tuple[str, list[WeekBlock]]:
    """Pull ``**Weeks N–M: Title.** body`` blocks out of the Evening A section.

    Returns ``(intro_body, blocks)`` — ``intro_body`` is any prose before the
    first week marker, typically empty but preserved just in case.
    """
    blocks: list[WeekBlock] = []
    first_match: re.Match | None = None
    for m in _WEEK_RE.finditer(evening_a_body):
        if first_match is None:
            first_match = m
        first_week = int(m.group(1))
        last_week = int(m.group(2)) if m.group(2) else first_week
        title = m.group(3).strip().rstrip(".")
        body = m.group(4).strip()
        blocks.append(
            WeekBlock(
                first_week=first_week,
                last_week=last_week,
                title=title,
                body=body,
            )
        )
    intro = (
        evening_a_body[: first_match.start()].strip()
        if first_match is not None
        else evening_a_body.strip()
    )
    return intro, blocks
