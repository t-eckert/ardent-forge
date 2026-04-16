"""StudioConnector — wraps the Course of Study syllabus and Art session logs.

Exposes the state an art-mentor agent (or Forge in chat) needs to coach the
user: what phase/week are we in, what should Evening A/B/C look like this
week, what has the user logged recently, and where do agent check-ins land.

The connector is notebook-only — reading the syllabus and session logs, and
writing new sessions + check-ins. It does not reach external services.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from forge.art import (
    CHECK_IN_DIR,
    SESSION_LOG_DIR,
    PhaseSchedule,
    StudioSessions,
    Syllabus,
    default_phase_schedule,
    parse_syllabus,
    resolve_focus,
)
from forge.connectors import Connector, Tool
from forge.notebook.errors import NotebookWriteError
from forge.notebook.reader import NotebookReader
from forge.notebook.writer import NotebookWriter

logger = logging.getLogger(__name__)

DEFAULT_SYLLABUS_PATH = "Artistic Course of Study.md"
# How many sessions to return per list call — small because the agent wants a
# readable window, not a dump.
MAX_LIST_ENTRIES = 30


class StudioConnector(Connector):
    name = "studio"

    def __init__(
        self,
        *,
        notebook_root: Path,
        phase_1_start: date,
        syllabus_path: str = DEFAULT_SYLLABUS_PATH,
    ) -> None:
        self._notebook_root = notebook_root
        self._syllabus_path = syllabus_path
        self._schedule: PhaseSchedule = default_phase_schedule(phase_1_start)
        self._reader: NotebookReader | None = None
        self._writer: NotebookWriter | None = None
        self._sessions: StudioSessions | None = None

    async def setup(self) -> None:
        try:
            reader = NotebookReader(self._notebook_root)
            writer = NotebookWriter(self._notebook_root)
            self._reader = reader
            self._writer = writer
            self._sessions = StudioSessions(reader, writer)
        except Exception:
            logger.exception(
                "StudioConnector notebook setup failed for %s", self._notebook_root
            )
            self._sessions = None

    async def health(self) -> bool:
        if self._sessions is None:
            return False
        # Require the syllabus file to exist so the connector only reports
        # healthy when current_focus / syllabus_read will actually return data.
        syllabus_path = self._notebook_root / self._syllabus_path
        return syllabus_path.is_file()

    @property
    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="studio_current_focus",
                description=(
                    "Resolve today's (or a given date's) place in the art syllabus. "
                    "Returns current phase, week-in-phase, Evening A drill "
                    "exercises, Evening B application guidance, Evening C master "
                    "studies, and the phase's checkpoint criteria. Use this at the "
                    "start of any coaching turn so you're coaching against the "
                    "right week, not generic advice."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "ISO date (YYYY-MM-DD). Defaults to today.",
                        }
                    },
                },
                execute=self._current_focus,
                connector_name=self.name,
            ),
            Tool(
                name="studio_syllabus_read",
                description=(
                    "Return the full Course of Study markdown, or one phase. Use this "
                    "when the user asks about the plan in general, or when you need "
                    "context beyond the current week (e.g. to connect this week's "
                    "drill to next phase's goals)."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "phase": {
                            "type": "integer",
                            "description": "Phase number (1–3). Omit for the full document.",
                        }
                    },
                },
                execute=self._syllabus_read,
                connector_name=self.name,
            ),
            Tool(
                name="studio_list_sessions",
                description=(
                    "List recent art session logs. Each entry includes the parsed "
                    "metadata (evening, phase, week, duration, materials, focus) "
                    "and any adjacent image paths. Call studio_get_session for the "
                    "full body."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Lookback window in days (default 14).",
                            "default": 14,
                        },
                        "evening": {
                            "type": "string",
                            "enum": ["A", "B", "C"],
                            "description": "Filter to one evening type. Omit for all.",
                        },
                    },
                },
                execute=self._list_sessions,
                connector_name=self.name,
            ),
            Tool(
                name="studio_get_session",
                description=(
                    "Fetch a single session log by path, including raw body and the "
                    "list of adjacent image files (same date prefix, same folder). "
                    "Use before giving feedback on a specific evening."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path, e.g. 'Fields/Art/Session Log/2026-04-14 Two-Value Studies.md'.",
                        }
                    },
                    "required": ["path"],
                },
                execute=self._get_session,
                connector_name=self.name,
            ),
            Tool(
                name="studio_log_session",
                description=(
                    "Write a new art session log. Creates Fields/Art/Session Log/"
                    "<date> <title>.md. Use when the user wants to record a session "
                    "they just finished — ask for duration, materials, and a short "
                    "reflection if they didn't volunteer them."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "ISO date (YYYY-MM-DD). Defaults to today.",
                        },
                        "title": {
                            "type": "string",
                            "description": "Short title, e.g. 'Two-Value Marker Studies'.",
                        },
                        "evening": {
                            "type": "string",
                            "enum": ["A", "B", "C"],
                            "description": "Evening type: A drill, B applied, C master study.",
                        },
                        "phase": {"type": "integer"},
                        "week": {"type": "integer"},
                        "duration_minutes": {"type": "integer"},
                        "materials": {"type": "string"},
                        "focus": {"type": "string"},
                        "body": {
                            "type": "string",
                            "description": "Main session content — what the user did.",
                        },
                        "reflection": {"type": "string"},
                    },
                    "required": ["title"],
                },
                execute=self._log_session,
                connector_name=self.name,
            ),
            Tool(
                name="studio_checkpoint",
                description=(
                    "Return the checkpoint criteria for a specific phase. Use when "
                    "the user is near the end of a phase so you know what 'ready for "
                    "next phase' actually means for them."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "phase": {"type": "integer", "description": "Phase number (1–3)."},
                    },
                    "required": ["phase"],
                },
                execute=self._checkpoint,
                connector_name=self.name,
            ),
            Tool(
                name="studio_list_checkins",
                description=(
                    "List past agent check-ins (weekly reviews, checkpoint "
                    "assessments, critiques). Each entry has a preview; read the "
                    "file with notebook_read for the full text."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Lookback window in days (default 60).",
                            "default": 60,
                        }
                    },
                },
                execute=self._list_checkins,
                connector_name=self.name,
            ),
        ]

    # ─── Internals ─────────────────────────────────────────────────────

    def _require_ready(self) -> dict | None:
        if self._reader is None or self._sessions is None:
            return {"error": "Notebook not configured or unavailable"}
        return None

    async def _load_syllabus(self) -> Syllabus | dict:
        err = self._require_ready()
        if err is not None:
            return err
        assert self._reader is not None
        try:
            body = await asyncio.to_thread(self._reader.read, self._syllabus_path)
        except FileNotFoundError:
            return {"error": f"Syllabus not found at {self._syllabus_path}"}
        except ValueError as exc:
            return {"error": str(exc)}
        return parse_syllabus(body)

    async def _current_focus(self, date: str | None = None) -> dict[str, Any]:
        syl = await self._load_syllabus()
        if isinstance(syl, dict):
            return syl
        try:
            resolved_date = (
                _parse_iso_date(date) if date else datetime.now(tz=timezone.utc).date()
            )
        except ValueError:
            return {"error": f"Invalid date '{date}' — use YYYY-MM-DD"}
        focus = resolve_focus(syl, self._schedule, resolved_date)
        if focus is None:
            return {
                "error": (
                    "Date is before the syllabus start. Phase 1 starts "
                    f"{self._schedule.anchors[0][1].isoformat()}."
                )
            }
        return focus.to_dict()

    async def _syllabus_read(self, phase: int | None = None) -> dict[str, Any]:
        syl = await self._load_syllabus()
        if isinstance(syl, dict):
            return syl
        if phase is None:
            return {"title": syl.title, "body": syl.raw}
        p = syl.phase(phase)
        if p is None:
            return {"error": f"No phase {phase} in syllabus"}
        return {
            "phase": p.number,
            "title": p.title,
            "date_range": p.date_range_label,
            "core_concept": p.core_concept,
            "evening_a_intro": p.evening_a_intro,
            "evening_a_weeks": [
                {
                    "weeks": f"{wb.first_week}–{wb.last_week}",
                    "title": wb.title,
                    "body": wb.body,
                }
                for wb in p.evening_a_weeks
            ],
            "evening_b": p.evening_b,
            "evening_c": p.evening_c,
            "checkpoint": p.checkpoint,
        }

    async def _list_sessions(
        self, days: int = 14, evening: str | None = None
    ) -> dict[str, Any]:
        err = self._require_ready()
        if err is not None:
            return err
        assert self._sessions is not None
        days = max(1, min(days, 365))
        since = datetime.now(tz=timezone.utc).date() - timedelta(days=days)
        entries = await asyncio.to_thread(self._sessions.list_sessions, since=since)
        if evening:
            evening = evening.upper()
            entries = [e for e in entries if e.evening == evening]
        entries = entries[:MAX_LIST_ENTRIES]
        return {
            "since": since.isoformat(),
            "count": len(entries),
            "entries": [
                {
                    "path": e.path,
                    "date": e.date.isoformat(),
                    "title": e.title,
                    "evening": e.evening,
                    "phase": e.phase,
                    "week": e.week,
                    "duration_minutes": e.duration_minutes,
                    "materials": e.materials,
                    "focus": e.focus,
                    "images": e.images,
                }
                for e in entries
            ],
        }

    async def _get_session(self, path: str) -> dict[str, Any]:
        err = self._require_ready()
        if err is not None:
            return err
        assert self._sessions is not None
        try:
            entry = await asyncio.to_thread(self._sessions.get_session, path)
        except FileNotFoundError:
            return {"error": f"Session not found: {path}"}
        except ValueError as exc:
            return {"error": str(exc)}
        return entry.to_dict()

    async def _log_session(
        self,
        *,
        title: str,
        date: str | None = None,
        evening: str | None = None,
        phase: int | None = None,
        week: int | None = None,
        duration_minutes: int | None = None,
        materials: str | None = None,
        focus: str | None = None,
        body: str = "",
        reflection: str | None = None,
    ) -> dict[str, Any]:
        err = self._require_ready()
        if err is not None:
            return err
        assert self._sessions is not None
        try:
            entry_date = (
                _parse_iso_date(date)
                if date
                else datetime.now(tz=timezone.utc).date()
            )
        except ValueError:
            return {"error": f"Invalid date '{date}' — use YYYY-MM-DD"}
        # If phase/week aren't supplied, backfill from the schedule so session
        # logs get tagged consistently even when the user doesn't remember.
        if phase is None or week is None:
            resolved = self._schedule.resolve(entry_date)
            if resolved is not None:
                if phase is None:
                    phase = resolved[0]
                if week is None:
                    week = resolved[1]
        try:
            rel = await asyncio.to_thread(
                self._sessions.create_session,
                entry_date=entry_date,
                title=title,
                evening=evening,
                phase=phase,
                week=week,
                duration_minutes=duration_minutes,
                materials=materials,
                focus=focus,
                body=body,
                reflection=reflection,
            )
        except NotebookWriteError as exc:
            return {"error": str(exc)}
        except ValueError as exc:
            return {"error": str(exc)}
        return {"path": rel, "status": "ok", "phase": phase, "week": week}

    async def _checkpoint(self, phase: int) -> dict[str, Any]:
        syl = await self._load_syllabus()
        if isinstance(syl, dict):
            return syl
        p = syl.phase(phase)
        if p is None:
            return {"error": f"No phase {phase} in syllabus"}
        return {
            "phase": p.number,
            "title": p.title,
            "checkpoint": p.checkpoint,
        }

    async def _list_checkins(self, days: int = 60) -> dict[str, Any]:
        err = self._require_ready()
        if err is not None:
            return err
        assert self._sessions is not None
        days = max(1, min(days, 730))
        since = datetime.now(tz=timezone.utc).date() - timedelta(days=days)
        entries = await asyncio.to_thread(
            self._sessions.list_check_ins, since=since
        )
        return {
            "since": since.isoformat(),
            "count": len(entries),
            "entries": entries[:MAX_LIST_ENTRIES],
            "directory": CHECK_IN_DIR,
            "session_log_directory": SESSION_LOG_DIR,
        }


def _parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)
