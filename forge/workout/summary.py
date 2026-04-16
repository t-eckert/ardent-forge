"""Weekly workout summary — aggregates Strava + notebook into a unified view.

Produces the ``health.workouts`` widget payload defined in
``ui/src/lib/schemas/widgets/workouts.ts``. That schema is running-block
shaped (threshold pace, long run, days-to-event), so for strength-only weeks
we fall back to placeholder strings rather than omitting required fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from forge.workout.notebook import WorkoutEntry
from forge.workout.strava import StravaActivity

# Metres per mile — we display US units since the user's notebook mixes them.
_METERS_PER_MILE = 1609.344
_METERS_PER_KM = 1000.0


@dataclass
class SessionRow:
    """One row in the widget's "recent sessions" list."""

    date_label: str
    title: str
    volume_label: str
    intensity_label: str
    source: str  # "strava" | "notebook"

    def to_widget_dict(self) -> dict:
        return {
            "dateLabel": self.date_label,
            "title": self.title,
            "volumeLabel": self.volume_label,
            "intensityLabel": self.intensity_label,
            "source": self.source,
        }


@dataclass
class WeeklySummary:
    """All the aggregated signal we hand to the widget.

    The widget payload has some running-centric fields (long_run, threshold_pace)
    that don't always apply — we fill placeholders rather than leave them off.
    """

    week_start: date
    week_end: date
    run_count: int
    strength_count: int
    total_distance_meters: float
    longest_run_meters: float
    total_duration_seconds: int
    rows: list[SessionRow]
    block_label: str
    goal: str
    event_label: str
    days_to_event: int
    threshold_pace_label: str

    def to_widget_payload(self) -> dict:
        """Map to the exact shape the UI schema validates against."""
        # The widget requires at least one row. If the week is truly empty we
        # emit a sentinel so the widget still renders instead of the caller
        # having to special-case it.
        rows = self.rows or [
            SessionRow(
                date_label="—",
                title="No sessions logged",
                volume_label="—",
                intensity_label="—",
                source="notebook",
            )
        ]
        return {
            "tool": "health.workouts",
            "blockLabel": self.block_label,
            "goal": self.goal,
            "daysToEvent": self.days_to_event,
            "eventLabel": self.event_label,
            "weekVolumeLabel": format_distance_miles(self.total_distance_meters),
            "longRunLabel": (
                format_distance_miles(self.longest_run_meters)
                if self.longest_run_meters > 0
                else "—"
            ),
            "thresholdPaceLabel": self.threshold_pace_label,
            "recent": [r.to_widget_dict() for r in rows],
            "sourcesLine": "sources: strava (live) · notebook (synced)",
        }


def format_distance_miles(meters: float) -> str:
    if meters <= 0:
        return "0 mi"
    miles = meters / _METERS_PER_MILE
    return f"{miles:.1f} mi"


def format_distance_km(meters: float) -> str:
    if meters <= 0:
        return "0 km"
    return f"{meters / _METERS_PER_KM:.1f} km"


def format_pace_per_mile(moving_seconds: int, meters: float) -> str:
    """Pace as mm:ss /mi. Returns '—' if inputs are missing."""
    if moving_seconds <= 0 or meters <= 0:
        return "—"
    miles = meters / _METERS_PER_MILE
    if miles <= 0:
        return "—"
    seconds_per_mile = moving_seconds / miles
    m = int(seconds_per_mile // 60)
    s = int(seconds_per_mile % 60)
    return f"{m}:{s:02d} /mi"


def format_duration(seconds: int) -> str:
    """Human duration: '45 min' or '1:02:30' for longer stuff."""
    if seconds < 3600:
        return f"{seconds // 60} min"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def _month_day(d: date) -> str:
    """Match the widget mock style ('Apr 10')."""
    return d.strftime("%b %d").replace(" 0", " ")


def _strava_start_date(activity: StravaActivity) -> date:
    try:
        return datetime.fromisoformat(activity.start_date.replace("Z", "+00:00")).date()
    except ValueError:
        return datetime.now(tz=timezone.utc).date()


def _is_run(sport_type: str) -> bool:
    return "run" in sport_type.lower()


def _is_strength(entry: WorkoutEntry) -> bool:
    """Heuristic: the notebook marks strength vs. run in the filename title."""
    t = entry.title.lower()
    return any(
        kw in t
        for kw in (
            "upper body",
            "lower body",
            "full body",
            "weight",
            "strength",
            "pull",
            "push",
            "legs",
        )
    )


def _strava_row(activity: StravaActivity) -> SessionRow:
    d = _strava_start_date(activity)
    volume_bits: list[str] = []
    if activity.distance_meters > 0:
        volume_bits.append(format_distance_miles(activity.distance_meters))
    if activity.moving_time_seconds > 0:
        volume_bits.append(format_duration(activity.moving_time_seconds))
    intensity_bits: list[str] = []
    if activity.average_heartrate:
        intensity_bits.append(f"{int(activity.average_heartrate)} bpm")
    if _is_run(activity.sport_type):
        pace = format_pace_per_mile(
            activity.moving_time_seconds, activity.distance_meters
        )
        if pace != "—":
            intensity_bits.append(pace)
    return SessionRow(
        date_label=_month_day(d),
        title=activity.name or activity.sport_type or "Activity",
        volume_label=" · ".join(volume_bits) if volume_bits else "—",
        intensity_label=" · ".join(intensity_bits) if intensity_bits else "—",
        source="strava",
    )


def _notebook_row(entry: WorkoutEntry) -> SessionRow:
    volume_bits: list[str] = []
    if entry.duration_minutes is not None:
        volume_bits.append(f"{entry.duration_minutes} min")
    return SessionRow(
        date_label=_month_day(entry.date),
        title=entry.title or entry.path,
        volume_label=" · ".join(volume_bits) if volume_bits else "—",
        intensity_label=entry.program or (entry.location or "—"),
        source="notebook",
    )


def build_weekly_summary(
    *,
    notebook_entries: Iterable[WorkoutEntry],
    strava_activities: Iterable[StravaActivity],
    week_start: date,
    block_label: str = "current week",
    goal: str = "—",
    event_label: str = "—",
    days_to_event: int = 0,
    threshold_pace_label: str = "—",
    max_rows: int = 6,
) -> WeeklySummary:
    """Build a ``WeeklySummary`` from raw notebook + Strava data.

    ``week_start`` is the inclusive date of the Monday (or whichever day the
    caller considers the week to begin). The window is 7 days. Any session
    outside is filtered out. Rows are sorted newest first and capped at
    ``max_rows`` to match what the widget can fit comfortably.
    """
    week_end = week_start + timedelta(days=6)

    filtered_nb = [e for e in notebook_entries if week_start <= e.date <= week_end]
    filtered_strava = [
        a for a in strava_activities if week_start <= _strava_start_date(a) <= week_end
    ]

    run_count = sum(1 for a in filtered_strava if _is_run(a.sport_type))
    # Notebook runs are hinted by filename/title too.
    run_count += sum(1 for e in filtered_nb if "run" in e.title.lower())
    strength_count = sum(1 for e in filtered_nb if _is_strength(e))

    total_distance = sum(a.distance_meters for a in filtered_strava)
    longest_run = max(
        (a.distance_meters for a in filtered_strava if _is_run(a.sport_type)),
        default=0.0,
    )
    total_duration = sum(a.moving_time_seconds for a in filtered_strava)
    total_duration += sum(
        (e.duration_minutes or 0) * 60 for e in filtered_nb
    )

    rows: list[SessionRow] = [_strava_row(a) for a in filtered_strava]
    rows.extend(_notebook_row(e) for e in filtered_nb)
    rows.sort(key=lambda r: r.date_label, reverse=True)
    rows = rows[:max_rows]

    return WeeklySummary(
        week_start=week_start,
        week_end=week_end,
        run_count=run_count,
        strength_count=strength_count,
        total_distance_meters=total_distance,
        longest_run_meters=longest_run,
        total_duration_seconds=total_duration,
        rows=rows,
        block_label=block_label,
        goal=goal,
        event_label=event_label,
        days_to_event=days_to_event,
        threshold_pace_label=threshold_pace_label,
    )
