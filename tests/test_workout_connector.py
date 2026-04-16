"""WorkoutConnector — tests the tool surface with a real notebook fixture
and a mocked Strava API. Covers the notebook-only path (create workout from
equipment), the Strava-integrated path (recent list + summary), and the
refresh-token rotation that's easy to get wrong.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest
import respx
from httpx import Response

from forge.connectors.workout import WorkoutConnector


pytestmark = pytest.mark.skipif(
    shutil.which("rg") is None, reason="ripgrep not installed"
)


# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def notebook(tmp_path: Path) -> Path:
    """Vault with one equipment note and two workout log entries."""
    root = tmp_path / "vault"
    log_dir = root / "Fields" / "Health" / "Workout Log"
    log_dir.mkdir(parents=True)

    (root / "Fields" / "Health" / "Fire Hall Gym.md").write_text(
        "# Fire Hall Gym\n"
        "\n"
        "## Equipment Available\n"
        "\n"
        "**Strength Training:**\n"
        "- Barbells\n"
        "- Dumbbells\n"
        "\n"
        "## Exercises by Equipment\n"
        "\n"
        "### Dumbbells\n"
        "| Muscle Group | Exercises |\n"
        "|--------------|-----------|\n"
        "| Chest | Dumbbell bench press |\n"
    )
    (root / "Fields" / "Health" / "Home Gym Equipment.md").write_text(
        "# Home Gym Equipment\n"
        "\n"
        "## Kettlebell\n"
        "\n"
        "## Equipment Available\n"
        "\n"
        "- Bowflex adjustable kettlebell\n"
    )
    (log_dir / "2026-04-14 Upper Body.md").write_text(
        "# Tue 14 April 2026\n"
        "\n"
        "**Duration:** 50 minutes\n"
        "**Program:** Workout A\n"
        "**Location:** [[Fire Hall Gym]]\n"
    )
    (log_dir / "2026-04-10 Run.md").write_text(
        "# Fri 10 April 2026\n"
        "\n"
        "**Duration:** 35 minutes\n"
        "**Program:** Easy Run\n"
    )
    return root


@pytest.fixture
async def connector(notebook: Path, tmp_path: Path) -> WorkoutConnector:
    c = WorkoutConnector(
        notebook_root=notebook,
        strava_client_id="client-id",
        strava_client_secret="client-secret",
        strava_refresh_token="seed-refresh",
        strava_token_path=tmp_path / "strava" / "tokens.json",
    )
    await c.setup()
    return c


# ─── Tool surface & health ─────────────────────────────────────────────


async def test_connector_exposes_expected_tools(connector: WorkoutConnector):
    names = {t.name for t in connector.tools}
    assert names == {
        "workout_list_recent",
        "workout_get",
        "workout_list_locations",
        "workout_get_location",
        "workout_create",
        "workout_weekly_summary",
    }
    assert all(t.connector_name == "workout" for t in connector.tools)


async def test_health_is_true_with_notebook(connector: WorkoutConnector):
    assert await connector.health() is True


async def test_health_is_false_without_notebook(tmp_path: Path):
    c = WorkoutConnector(notebook_root=tmp_path / "missing")
    await c.setup()
    assert await c.health() is False


# ─── Locations & equipment ─────────────────────────────────────────────


async def test_list_locations_returns_both_gyms(connector: WorkoutConnector):
    result = await connector._list_locations()
    names = {loc["name"] for loc in result["locations"]}
    assert names == {"Fire Hall Gym", "Home"}


async def test_get_location_is_case_insensitive(connector: WorkoutConnector):
    result = await connector._get_location(name="fire hall gym")
    assert result["name"] == "Fire Hall Gym"
    # Equipment + exercises both present so the agent has enough to compose a workout.
    assert any("Barbells" in e for e in result["equipment"])
    assert "Dumbbells" in result["exercises_by_equipment"]


async def test_get_location_unknown_returns_error(connector: WorkoutConnector):
    result = await connector._get_location(name="Mars Colony")
    assert "error" in result


# ─── Creating workouts ────────────────────────────────────────────────


async def test_create_writes_file_in_workout_log(
    connector: WorkoutConnector, notebook: Path
):
    result = await connector._create(
        date="2026-04-17",
        title="Full Body",
        location="Fire Hall Gym",
        duration_minutes=45,
        program="Workout C",
        sections=[["Warm Up", "5 min bike"], ["Strength", "Dumbbell bench 3x10"]],
        notes="Felt good.",
    )
    assert result["status"] == "ok"
    expected = "Fields/Health/Workout Log/2026-04-17 Full Body.md"
    assert result["path"] == expected
    written = (notebook / expected).read_text()
    assert "**Duration:** 45 minutes" in written
    assert "**Location:** [[Fire Hall Gym]]" in written
    assert "## Warm Up" in written
    assert "Dumbbell bench 3x10" in written


async def test_create_rejects_duplicate_without_overwrite(
    connector: WorkoutConnector,
):
    # There's an existing "2026-04-14 Upper Body.md" in the fixture.
    result = await connector._create(
        date="2026-04-14",
        title="Upper Body",
        duration_minutes=45,
    )
    assert "error" in result
    assert "already exists" in result["error"]


async def test_create_rejects_malformed_date(connector: WorkoutConnector):
    result = await connector._create(date="not-a-date", title="x")
    assert "Invalid date" in result["error"]


async def test_create_validates_section_shape(connector: WorkoutConnector):
    result = await connector._create(
        date="2026-04-18",
        title="Bad",
        sections=[["only-one-element"]],  # malformed — agent must supply [head, body]
    )
    assert "error" in result


# ─── Notebook-side reads ───────────────────────────────────────────────


async def test_list_recent_returns_notebook_entries(connector: WorkoutConnector):
    result = await connector._list_recent(days=60, source="notebook")
    titles = {e["title"] for e in result["entries"]}
    assert "Upper Body" in titles
    assert "Run" in titles
    # Newest first: April 14 entry should sort before April 10.
    dates = [e["date"] for e in result["entries"]]
    assert dates == sorted(dates, reverse=True)


async def test_get_notebook_returns_raw_body(connector: WorkoutConnector):
    result = await connector._get(
        source="notebook",
        id="Fields/Health/Workout Log/2026-04-14 Upper Body.md",
    )
    assert result["duration_minutes"] == 50
    assert "Workout A" in result["program"]
    assert "**Location:**" in result["raw"]


async def test_get_notebook_returns_error_when_missing(connector: WorkoutConnector):
    result = await connector._get(source="notebook", id="Fields/Health/Workout Log/nope.md")
    assert "error" in result


# ─── Strava integration (mocked) ───────────────────────────────────────


def _mock_strava_token_exchange():
    """Install a mock that returns rotated tokens with an hour of runway."""
    expires_at = int(time.time()) + 3600
    return respx.post("https://www.strava.com/oauth/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_at": expires_at,
                "token_type": "Bearer",
            },
        )
    )


@respx.mock
async def test_strava_list_recent_refreshes_token_and_persists(
    connector: WorkoutConnector, tmp_path: Path
):
    _mock_strava_token_exchange()
    respx.get("https://www.strava.com/api/v3/athlete/activities").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 12345,
                    "name": "Morning Run",
                    "type": "Run",
                    "sport_type": "Run",
                    "start_date": "2026-04-15T12:00:00Z",
                    "elapsed_time": 2700,
                    "moving_time": 2700,
                    "distance": 8000.0,
                    "average_heartrate": 150.0,
                    "max_heartrate": 170.0,
                    "average_speed": 2.96,
                }
            ],
        )
    )
    result = await connector._list_recent(days=7, source="strava")
    assert result["count"] == 1
    assert result["entries"][0]["source"] == "strava"
    assert result["entries"][0]["id"] == 12345

    # Critical: the new refresh token was persisted. Losing it here means the
    # next boot can't exchange for a fresh access token.
    token_file = tmp_path / "strava" / "tokens.json"
    assert token_file.exists()
    persisted = json.loads(token_file.read_text())
    assert persisted["refresh_token"] == "new-refresh"
    assert persisted["access_token"] == "new-access"


@respx.mock
async def test_strava_get_activity_by_id(connector: WorkoutConnector):
    _mock_strava_token_exchange()
    respx.get("https://www.strava.com/api/v3/activities/99").mock(
        return_value=Response(
            200,
            json={
                "id": 99,
                "name": "Tempo",
                "type": "Run",
                "sport_type": "TempoRun",
                "start_date": "2026-04-15T12:00:00Z",
                "elapsed_time": 3000,
                "moving_time": 3000,
                "distance": 10000.0,
                "average_heartrate": 165.0,
                "max_heartrate": 180.0,
                "average_speed": 3.33,
            },
        )
    )
    result = await connector._get(source="strava", id="99")
    assert result["id"] == 99
    assert result["sport_type"] == "TempoRun"
    assert result["distance_meters"] == pytest.approx(10000.0)


async def test_strava_tools_degrade_gracefully_without_credentials(
    notebook: Path, tmp_path: Path
):
    # No Strava creds at all — notebook still works, Strava paths return errors.
    c = WorkoutConnector(
        notebook_root=notebook, strava_token_path=tmp_path / "t.json"
    )
    await c.setup()
    listed = await c._list_recent(days=7, source="strava")
    assert listed.get("strava_error") == "Strava not configured"
    got = await c._get(source="strava", id="1")
    assert got == {"error": "Strava not configured"}
    # Notebook side still healthy.
    assert await c.health() is True


# ─── Weekly summary ────────────────────────────────────────────────────


@respx.mock
async def test_weekly_summary_combines_strava_and_notebook(connector: WorkoutConnector):
    _mock_strava_token_exchange()
    respx.get("https://www.strava.com/api/v3/athlete/activities").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 1,
                    "name": "Easy run",
                    "type": "Run",
                    "sport_type": "Run",
                    "start_date": "2026-04-15T12:00:00Z",
                    "elapsed_time": 2400,
                    "moving_time": 2400,
                    "distance": 6000.0,
                    "average_heartrate": 145.0,
                    "max_heartrate": 160.0,
                    "average_speed": 2.5,
                }
            ],
        )
    )
    result = await connector._weekly_summary(
        week_start="2026-04-13",
        goal="Sub-50",
        event_label="Tamarack 10K",
        event_date="2026-05-07",
        block_label="10K build · wk 9",
    )
    assert result["run_count"] == 1
    # Upper Body notebook entry from 2026-04-14 is inside the week window.
    assert result["strength_count"] == 1
    widget = result["widget"]
    assert widget["tool"] == "health.workouts"
    assert widget["eventLabel"] == "Tamarack 10K"
    assert widget["goal"] == "Sub-50"
    # At least the two sessions appear in the recent feed.
    assert len(widget["recent"]) >= 2
    sources = {row["source"] for row in widget["recent"]}
    assert "strava" in sources
    assert "notebook" in sources


async def test_weekly_summary_rejects_malformed_dates(connector: WorkoutConnector):
    result = await connector._weekly_summary(week_start="not-a-date")
    assert "error" in result
