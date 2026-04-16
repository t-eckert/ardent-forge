"""Workout domain — notebook parsing, Strava client, and session aggregation.

Kept separate from forge/connectors/workout.py so the domain logic is
testable without the Connector shell around it. The connector is the
async tool surface; everything here is reusable lower-level machinery.
"""

from forge.workout.notebook import (
    EquipmentLocation,
    NotebookWorkouts,
    WorkoutEntry,
    parse_equipment_markdown,
    parse_workout_markdown,
    render_workout_template,
)
from forge.workout.strava import StravaActivity, StravaClient, StravaTokenStore
from forge.workout.summary import SessionRow, WeeklySummary, build_weekly_summary

__all__ = [
    "EquipmentLocation",
    "NotebookWorkouts",
    "SessionRow",
    "StravaActivity",
    "StravaClient",
    "StravaTokenStore",
    "WeeklySummary",
    "WorkoutEntry",
    "build_weekly_summary",
    "parse_equipment_markdown",
    "parse_workout_markdown",
    "render_workout_template",
]
