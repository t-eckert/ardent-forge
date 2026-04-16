"""WorkoutConnector — unified surface over the notebook's workout logs
and Strava's API.

Exposes six tools:

* ``workout_list_recent`` — unified feed of recent sessions from both sources
* ``workout_get`` — full content of one notebook log or Strava activity
* ``workout_list_locations`` — summary of gyms/equipment defined in the notebook
* ``workout_get_location`` — full equipment detail for one location
* ``workout_create`` — write a new notebook log file (agent composes from equipment)
* ``workout_weekly_summary`` — aggregated weekly stats + widget payload

Designed so the agent reads equipment, composes a workout, and writes it back
in a single chat turn: ``workout_get_location`` → reason → ``workout_create``.
Strava is read-only — we never push activities there.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from forge.connectors import Connector, Tool
from forge.notebook.errors import NotebookWriteError
from forge.notebook.reader import NotebookReader
from forge.notebook.writer import NotebookWriter
from forge.workout import (
    NotebookWorkouts,
    StravaClient,
    StravaTokenStore,
    build_weekly_summary,
)

logger = logging.getLogger(__name__)

# Soft limits to keep tool payloads inside Claude's attention budget.
_MAX_LIST_ENTRIES = 30
_DEFAULT_LIST_DAYS = 14


class WorkoutConnector(Connector):
    name = "workout"

    def __init__(
        self,
        *,
        notebook_root: Path,
        strava_client_id: str = "",
        strava_client_secret: str = "",
        strava_refresh_token: str = "",
        strava_token_path: Path | None = None,
    ) -> None:
        self._notebook_root = notebook_root
        self._strava_client_id = strava_client_id
        self._strava_client_secret = strava_client_secret
        self._strava_refresh_token = strava_refresh_token
        self._strava_token_path = strava_token_path or (
            notebook_root.parent / "strava" / "tokens.json"
        )
        self._workouts: NotebookWorkouts | None = None
        self._strava: StravaClient | None = None

    async def setup(self) -> None:
        # Notebook layer — same lazy pattern as NotebookConnector. If the vault
        # isn't there at boot we just report unhealthy rather than crash.
        try:
            reader = NotebookReader(self._notebook_root)
            writer = NotebookWriter(self._notebook_root)
            self._workouts = NotebookWorkouts(reader, writer)
        except Exception:
            logger.exception(
                "WorkoutConnector notebook setup failed for %s", self._notebook_root
            )
            self._workouts = None

        # Strava layer — credentials are optional. The connector degrades to
        # notebook-only mode when they're missing.
        if self._strava_client_id and self._strava_client_secret:
            store = StravaTokenStore(
                self._strava_token_path,
                seed_refresh_token=self._strava_refresh_token or None,
            )
            client = StravaClient(
                client_id=self._strava_client_id,
                client_secret=self._strava_client_secret,
                token_store=store,
            )
            if client.configured():
                self._strava = client
            else:
                logger.warning(
                    "Strava credentials present but no refresh token — "
                    "set FORGE_STRAVA_REFRESH_TOKEN or restore the token file"
                )
                self._strava = None
        else:
            self._strava = None

    async def health(self) -> bool:
        # Unhealthy only if the notebook is unavailable. Strava being missing
        # is a soft degradation — the connector still works for notebook flows.
        return self._workouts is not None

    @property
    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="workout_list_recent",
                description=(
                    "List recent workouts from the notebook log and Strava, newest first. "
                    "Use when the user asks about training the past week/month, or when "
                    "building a weekly summary. Each entry includes source, date, title, "
                    "and top-line volume. Call workout_get for full content."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Lookback window in days (default 14).",
                            "default": _DEFAULT_LIST_DAYS,
                        },
                        "source": {
                            "type": "string",
                            "enum": ["all", "notebook", "strava"],
                            "description": "Restrict to one source. Default 'all'.",
                            "default": "all",
                        },
                    },
                },
                execute=self._list_recent,
                connector_name=self.name,
            ),
            Tool(
                name="workout_get",
                description=(
                    "Fetch one workout in full. For the notebook, pass source='notebook' "
                    "and id=<relative path> (e.g. 'Fields/Health/Workout Log/2026-03-31 Run.md'). "
                    "For Strava, pass source='strava' and id=<activity id as string>."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "enum": ["notebook", "strava"],
                        },
                        "id": {
                            "type": "string",
                            "description": "Relative path (notebook) or activity id (strava).",
                        },
                    },
                    "required": ["source", "id"],
                },
                execute=self._get,
                connector_name=self.name,
            ),
            Tool(
                name="workout_list_locations",
                description=(
                    "List the training locations defined in the notebook (gyms, home setup), "
                    "with their equipment. Use this before composing a new workout so you "
                    "only prescribe exercises the user can actually do at the chosen location."
                ),
                input_schema={"type": "object", "properties": {}},
                execute=self._list_locations,
                connector_name=self.name,
            ),
            Tool(
                name="workout_get_location",
                description=(
                    "Fetch the full equipment detail for one training location. Includes the "
                    "structured exercise-by-equipment tables plus the raw note for anything the "
                    "parser didn't surface (hours, membership, notes)."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Location name, e.g. 'Fire Hall Gym' or 'Home'.",
                        }
                    },
                    "required": ["name"],
                },
                execute=self._get_location,
                connector_name=self.name,
            ),
            Tool(
                name="workout_create",
                description=(
                    "Create a new workout log entry in the notebook. Use after reading the "
                    "location's equipment so the composed workout only uses available gear. "
                    "'sections' is a list of [heading, body] pairs for Warm Up / Strength / "
                    "Cool Down etc. Writes to Fields/Health/Workout Log/<date> <title>.md; "
                    "refuses to overwrite an existing file unless overwrite=true."
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
                            "description": "Short title, e.g. 'Upper Body' or 'Run'.",
                        },
                        "location": {
                            "type": "string",
                            "description": "Location name (wikilinked in the body). Optional.",
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Planned duration. Optional.",
                        },
                        "program": {
                            "type": "string",
                            "description": "Program label e.g. 'Workout B (Pull + Hinge)'. Optional.",
                        },
                        "sections": {
                            "type": "array",
                            "description": "Ordered [heading, body] pairs for the workout structure.",
                            "items": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 2,
                                "maxItems": 2,
                            },
                        },
                        "notes": {
                            "type": "string",
                            "description": "Freeform notes appended after the sections. Optional.",
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "Allow overwriting an existing entry. Default false.",
                            "default": False,
                        },
                    },
                    "required": ["title"],
                },
                execute=self._create,
                connector_name=self.name,
            ),
            Tool(
                name="workout_weekly_summary",
                description=(
                    "Aggregate this week's (or a specific week's) workouts into counts, volume, "
                    "and a widget-ready payload for the chat UI. Strava contributes runs and "
                    "heart rate; notebook contributes strength sessions. Pass week_start to "
                    "anchor a specific week; omit for the current ISO week."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "week_start": {
                            "type": "string",
                            "description": "ISO date for the first day of the week. Defaults to this Monday.",
                        },
                        "goal": {
                            "type": "string",
                            "description": "Training goal to display on the widget.",
                        },
                        "event_label": {
                            "type": "string",
                            "description": "Name of the target event, e.g. 'Tamarack 10K'.",
                        },
                        "event_date": {
                            "type": "string",
                            "description": "ISO date of the event — drives days_to_event.",
                        },
                        "block_label": {
                            "type": "string",
                            "description": "Training block label, e.g. '10K build · wk 9/14'.",
                        },
                    },
                },
                execute=self._weekly_summary,
                connector_name=self.name,
                to_widget=self._summary_to_widget,
            ),
        ]

    # ─── Tool implementations ──────────────────────────────────────────

    def _require_workouts(self) -> NotebookWorkouts | dict:
        if self._workouts is None:
            return {"error": "Notebook not configured or unavailable"}
        return self._workouts

    async def _list_recent(
        self, days: int = _DEFAULT_LIST_DAYS, source: str = "all"
    ) -> dict[str, Any]:
        w = self._require_workouts()
        if isinstance(w, dict):
            return w
        days = max(1, min(days, 365))
        since = (datetime.now(tz=timezone.utc).date() - timedelta(days=days))

        notebook_entries: list[dict] = []
        if source in ("all", "notebook"):
            entries = await asyncio.to_thread(w.list_entries, since=since)
            for e in entries[:_MAX_LIST_ENTRIES]:
                notebook_entries.append(
                    {
                        "source": "notebook",
                        "date": e.date.isoformat(),
                        "title": e.title,
                        "path": e.path,
                        "duration_minutes": e.duration_minutes,
                        "program": e.program,
                        "location": e.location,
                    }
                )

        strava_entries: list[dict] = []
        strava_error: str | None = None
        if source in ("all", "strava"):
            if self._strava is None:
                strava_error = "Strava not configured"
            else:
                try:
                    after_ts = int(
                        datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc).timestamp()
                    )
                    acts = await self._strava.list_recent_activities(
                        after=after_ts, per_page=_MAX_LIST_ENTRIES
                    )
                except Exception as exc:  # noqa: BLE001 — surface to Claude
                    logger.exception("Strava list failed")
                    strava_error = f"Strava fetch failed: {exc}"
                    acts = []
                for a in acts:
                    strava_entries.append(
                        {
                            "source": "strava",
                            "id": a.id,
                            "date": a.start_date[:10],
                            "title": a.name,
                            "type": a.type,
                            "sport_type": a.sport_type,
                            "distance_meters": a.distance_meters,
                            "moving_time_seconds": a.moving_time_seconds,
                            "average_heartrate": a.average_heartrate,
                        }
                    )

        combined = sorted(
            notebook_entries + strava_entries,
            key=lambda r: r.get("date", ""),
            reverse=True,
        )[:_MAX_LIST_ENTRIES]

        out: dict[str, Any] = {
            "since": since.isoformat(),
            "count": len(combined),
            "entries": combined,
        }
        if strava_error is not None:
            out["strava_error"] = strava_error
        return out

    async def _get(self, source: str, id: str) -> dict[str, Any]:
        if source == "notebook":
            w = self._require_workouts()
            if isinstance(w, dict):
                return w
            try:
                entry = await asyncio.to_thread(w.get_entry, id)
            except FileNotFoundError:
                return {"error": f"Notebook entry not found: {id}"}
            except ValueError as exc:
                return {"error": str(exc)}
            return entry.to_dict()
        if source == "strava":
            if self._strava is None:
                return {"error": "Strava not configured"}
            try:
                activity_id = int(id)
            except ValueError:
                return {"error": f"Invalid Strava activity id: {id}"}
            try:
                activity = await self._strava.get_activity(activity_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Strava get failed")
                return {"error": f"Strava fetch failed: {exc}"}
            return activity.to_dict()
        return {"error": f"Unknown source: {source}"}

    async def _list_locations(self) -> dict[str, Any]:
        w = self._require_workouts()
        if isinstance(w, dict):
            return w
        locations = await asyncio.to_thread(w.list_locations)
        return {
            "locations": [
                {
                    "name": loc.name,
                    "path": loc.path,
                    "equipment_count": len(loc.equipment),
                    "equipment_preview": loc.equipment[:8],
                    "categories": list(loc.exercises_by_equipment.keys()),
                }
                for loc in locations
            ]
        }

    async def _get_location(self, name: str) -> dict[str, Any]:
        w = self._require_workouts()
        if isinstance(w, dict):
            return w
        loc = await asyncio.to_thread(w.get_location, name)
        if loc is None:
            return {"error": f"Unknown location: {name}"}
        return loc.to_dict()

    async def _create(
        self,
        *,
        title: str,
        date: str | None = None,
        location: str | None = None,
        duration_minutes: int | None = None,
        program: str | None = None,
        sections: list[list[str]] | None = None,
        notes: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        w = self._require_workouts()
        if isinstance(w, dict):
            return w
        try:
            entry_date = (
                _parse_iso_date(date)
                if date
                else datetime.now(tz=timezone.utc).date()
            )
        except ValueError:
            return {"error": f"Invalid date '{date}' — use YYYY-MM-DD"}

        typed_sections: list[tuple[str, str]] | None = None
        if sections is not None:
            typed_sections = []
            for pair in sections:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    return {"error": "Each section must be a [heading, body] pair"}
                typed_sections.append((str(pair[0]), str(pair[1])))

        try:
            rel = await asyncio.to_thread(
                w.create_entry,
                entry_date=entry_date,
                title=title,
                location=location,
                duration_minutes=duration_minutes,
                program=program,
                sections=typed_sections,
                notes=notes,
                overwrite=overwrite,
            )
        except NotebookWriteError as exc:
            return {"error": str(exc)}
        except ValueError as exc:
            return {"error": str(exc)}
        return {"path": rel, "status": "ok"}

    async def _weekly_summary(
        self,
        *,
        week_start: str | None = None,
        goal: str = "—",
        event_label: str = "—",
        event_date: str | None = None,
        block_label: str = "current week",
    ) -> dict[str, Any]:
        w = self._require_workouts()
        if isinstance(w, dict):
            return w

        today = datetime.now(tz=timezone.utc).date()
        if week_start is not None:
            try:
                start = _parse_iso_date(week_start)
            except ValueError:
                return {"error": f"Invalid week_start '{week_start}' — use YYYY-MM-DD"}
        else:
            start = today - timedelta(days=today.weekday())  # Monday of this week

        days_to_event = 0
        if event_date:
            try:
                target = _parse_iso_date(event_date)
                days_to_event = max(0, (target - today).days)
            except ValueError:
                return {"error": f"Invalid event_date '{event_date}' — use YYYY-MM-DD"}

        # Pull in all notebook entries from the week window.
        entries = await asyncio.to_thread(
            w.list_entries, since=start
        )
        # Strava is optional. Failures are degraded — we still ship the widget
        # with whatever we have from the notebook.
        strava_acts = []
        strava_error: str | None = None
        if self._strava is not None:
            try:
                after_ts = int(
                    datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp()
                )
                strava_acts = await self._strava.list_recent_activities(
                    after=after_ts, per_page=50
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Strava weekly fetch failed")
                strava_error = f"Strava fetch failed: {exc}"

        summary = build_weekly_summary(
            notebook_entries=entries,
            strava_activities=strava_acts,
            week_start=start,
            block_label=block_label,
            goal=goal,
            event_label=event_label,
            days_to_event=days_to_event,
        )
        out = {
            "week_start": summary.week_start.isoformat(),
            "week_end": summary.week_end.isoformat(),
            "run_count": summary.run_count,
            "strength_count": summary.strength_count,
            "total_distance_meters": summary.total_distance_meters,
            "longest_run_meters": summary.longest_run_meters,
            "total_duration_seconds": summary.total_duration_seconds,
            "widget": summary.to_widget_payload(),
        }
        if strava_error is not None:
            out["strava_error"] = strava_error
        return out

    @staticmethod
    def _summary_to_widget(result: dict) -> dict | None:
        """Tool-result → widget payload indirection.

        The connector returns the full summary plus a pre-built widget dict; the
        widget renderer wants just the ``health.workouts`` payload. Pulls it out
        so the UI doesn't need to know the tool's aggregate shape.
        """
        if "error" in result:
            return None
        widget = result.get("widget")
        if not isinstance(widget, dict):
            return None
        return widget


def _parse_iso_date(value: str) -> date:
    """Parse 'YYYY-MM-DD'. Raises ValueError on anything else."""
    return date.fromisoformat(value)
