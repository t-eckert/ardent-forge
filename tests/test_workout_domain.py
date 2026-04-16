"""Domain-level tests for forge.workout — parsers, template renderer,
and the weekly-summary aggregator. These exercise the pure-Python logic
without any Connector or HTTP wiring.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from forge.workout import (
    StravaActivity,
    build_weekly_summary,
    parse_equipment_markdown,
    parse_workout_markdown,
    render_workout_template,
)
from forge.workout.strava import StravaTokens, StravaTokenStore


# ─── Workout markdown parser ───────────────────────────────────────────


def test_parse_workout_extracts_date_and_metadata():
    body = (
        "# Tue 27 January 2026\n"
        "\n"
        "**Duration:** 45 minutes\n"
        "**Program:** Workout B (Pull + Hinge)\n"
        "**Location:** [[Fire Hall Gym]]\n"
        "\n"
        "## Warm Up\n"
    )
    entry = parse_workout_markdown(
        "Fields/Health/Workout Log/2026-01-28 Full Body.md", body
    )
    assert entry.date == date(2026, 1, 28)
    assert entry.title == "Full Body"
    assert entry.duration_minutes == 45
    assert entry.program == "Workout B (Pull + Hinge)"
    # Wikilink stripped so the string is useful in tool payloads.
    assert entry.location == "Fire Hall Gym"


def test_parse_workout_handles_hour_durations():
    body = "**Duration:** 1.5 hours\n"
    entry = parse_workout_markdown("Fields/Health/Workout Log/2026-04-01 Ride.md", body)
    assert entry.duration_minutes == 90


def test_parse_workout_rejects_non_date_filename():
    with pytest.raises(ValueError):
        parse_workout_markdown("Fields/Health/Workout Log/random.md", "body")


def test_parse_workout_leaves_raw_body_intact():
    body = "# 2026-04-01\n\n**Duration:** 30 min\n\nfreeform notes\n"
    entry = parse_workout_markdown("Fields/Health/Workout Log/2026-04-01 Run.md", body)
    assert entry.raw == body


# ─── Equipment parser ──────────────────────────────────────────────────


def test_parse_equipment_extracts_items_and_exercise_tables():
    body = (
        "# Fire Hall Gym\n"
        "\n"
        "## Equipment Available\n"
        "\n"
        "**Cardio Equipment:**\n"
        "- 2 Treadmills\n"
        "- 1 Rower\n"
        "\n"
        "**Strength Training:**\n"
        "- 1 Functional Cable Machine\n"
        "- Barbells\n"
        "\n"
        "## Exercises by Equipment\n"
        "\n"
        "### Cable Machine\n"
        "| Muscle Group | Exercises |\n"
        "|--------------|-----------|\n"
        "| Chest | Cable flyes, cable crossover |\n"
        "| Back | Lat pulldown, cable row |\n"
        "\n"
        "### Dumbbells\n"
        "| Muscle Group | Exercises |\n"
        "|--------------|-----------|\n"
        "| Chest | Dumbbell bench press |\n"
        "\n"
        "## Notes\n"
        "Some trailing note content.\n"
    )
    loc = parse_equipment_markdown("Fire Hall Gym", "Fields/Health/Fire Hall Gym.md", body)
    assert loc.name == "Fire Hall Gym"
    # Category prefix preserved so the agent can reason about cardio vs strength.
    assert "Cardio Equipment: 2 Treadmills" in loc.equipment
    assert "Strength Training: Barbells" in loc.equipment
    assert list(loc.exercises_by_equipment.keys()) == ["Cable Machine", "Dumbbells"]
    assert loc.exercises_by_equipment["Cable Machine"] == [
        "Chest — Cable flyes, cable crossover",
        "Back — Lat pulldown, cable row",
    ]
    # Raw kept so the agent can read sections the parser doesn't know about.
    assert "Some trailing note content" in loc.raw


def test_parse_equipment_is_tolerant_of_missing_sections():
    loc = parse_equipment_markdown("Empty", "Fields/Health/Empty.md", "# Empty\nNothing here.\n")
    assert loc.equipment == []
    assert loc.exercises_by_equipment == {}


# ─── Template renderer ─────────────────────────────────────────────────


def test_render_template_includes_all_metadata_and_sections():
    text = render_workout_template(
        entry_date=date(2026, 4, 16),
        location="Fire Hall Gym",
        duration_minutes=45,
        program="Workout B",
        sections=[("Warm Up", "- 5 min bike"), ("Strength", "- Row 3x10")],
        notes="Felt strong.",
    )
    assert "# Thu 16 April 2026" in text
    assert "**Duration:** 45 minutes" in text
    assert "**Program:** Workout B" in text
    # Location is wikilinked so Obsidian resolves it back to the gym note.
    assert "**Location:** [[Fire Hall Gym]]" in text
    assert "**Daily Log:** [[2026-04-16]]" in text
    assert "## Warm Up" in text
    assert "- 5 min bike" in text
    assert "## Strength" in text
    assert "## Notes" in text
    assert "Felt strong." in text


def test_render_template_omits_fields_when_none():
    text = render_workout_template(
        entry_date=date(2026, 4, 16),
        location=None,
        duration_minutes=None,
        program=None,
    )
    assert "**Duration:**" not in text
    assert "**Program:**" not in text
    assert "**Location:**" not in text
    # Daily Log backlink is always present — it's how the notebook cross-links.
    assert "**Daily Log:** [[2026-04-16]]" in text


# ─── Strava token store ────────────────────────────────────────────────


def test_token_store_roundtrips_tokens(tmp_path: Path):
    path = tmp_path / "tokens.json"
    store = StravaTokenStore(path, seed_refresh_token="seed")
    assert store.load() is None
    # Seed is available until something is persisted.
    assert store.initial_refresh_token() == "seed"

    tokens = StravaTokens(access_token="a", refresh_token="r", expires_at=1700000000)
    store.save(tokens)
    loaded = store.load()
    assert loaded is not None
    assert loaded.access_token == "a"
    assert loaded.refresh_token == "r"
    assert loaded.expires_at == 1700000000
    # File written atomically — no leftover .tmp.
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_token_store_ignores_malformed_file(tmp_path: Path):
    path = tmp_path / "tokens.json"
    path.write_text("not json")
    store = StravaTokenStore(path)
    assert store.load() is None


def test_token_store_save_format(tmp_path: Path):
    path = tmp_path / "tokens.json"
    store = StravaTokenStore(path)
    tokens = StravaTokens(access_token="a", refresh_token="r", expires_at=42)
    store.save(tokens)
    data = json.loads(path.read_text())
    assert data == {"access_token": "a", "refresh_token": "r", "expires_at": 42}


# ─── Weekly summary aggregator ─────────────────────────────────────────


def _strava_run(start: datetime, distance_m: float, duration_s: int, hr: float) -> StravaActivity:
    return StravaActivity.from_api(
        {
            "id": int(start.timestamp()),
            "name": "Tempo run",
            "type": "Run",
            "sport_type": "TempoRun",
            "start_date": start.isoformat().replace("+00:00", "Z"),
            "elapsed_time": duration_s,
            "moving_time": duration_s,
            "distance": distance_m,
            "average_heartrate": hr,
            "max_heartrate": hr + 10,
            "average_speed": distance_m / max(duration_s, 1),
        }
    )


def test_weekly_summary_aggregates_distance_and_counts():
    from forge.workout.notebook import WorkoutEntry

    week_start = date(2026, 4, 13)  # Monday
    notebook_entries = [
        WorkoutEntry(
            path="Fields/Health/Workout Log/2026-04-14 Upper Body.md",
            date=date(2026, 4, 14),
            title="Upper Body",
            duration_minutes=50,
            program="Program A",
            location="Fire Hall Gym",
            raw="",
        ),
        # Out-of-window entry — must be excluded from totals.
        WorkoutEntry(
            path="Fields/Health/Workout Log/2026-04-06 Upper Body.md",
            date=date(2026, 4, 6),
            title="Upper Body",
            duration_minutes=45,
            program=None,
            location=None,
            raw="",
        ),
    ]
    strava = [
        _strava_run(datetime(2026, 4, 15, 7, tzinfo=timezone.utc), 8000.0, 2700, 150.0),
        _strava_run(datetime(2026, 4, 18, 9, tzinfo=timezone.utc), 12000.0, 4200, 158.0),
    ]

    summary = build_weekly_summary(
        notebook_entries=notebook_entries,
        strava_activities=strava,
        week_start=week_start,
        event_label="Tamarack 10K",
        days_to_event=21,
        goal="Sub-50",
        block_label="10K build · wk 9/14",
    )

    assert summary.run_count == 2
    assert summary.strength_count == 1
    assert summary.total_distance_meters == pytest.approx(20000.0)
    assert summary.longest_run_meters == pytest.approx(12000.0)
    assert summary.total_duration_seconds == 2700 + 4200 + 50 * 60

    widget = summary.to_widget_payload()
    assert widget["tool"] == "health.workouts"
    assert widget["goal"] == "Sub-50"
    assert widget["eventLabel"] == "Tamarack 10K"
    assert widget["daysToEvent"] == 21
    # 20000 m ≈ 12.4 mi; check the rendered format rather than the exact float.
    assert widget["weekVolumeLabel"].endswith("mi")
    assert widget["longRunLabel"].endswith("mi")
    assert len(widget["recent"]) >= 1


def test_weekly_summary_empty_week_still_renders_widget():
    summary = build_weekly_summary(
        notebook_entries=[],
        strava_activities=[],
        week_start=date(2026, 4, 13),
    )
    widget = summary.to_widget_payload()
    # Widget requires at least one row; the aggregator inserts a sentinel.
    assert len(widget["recent"]) == 1
    assert widget["recent"][0]["title"] == "No sessions logged"
    assert widget["weekVolumeLabel"] == "0 mi"
    assert widget["longRunLabel"] == "—"
