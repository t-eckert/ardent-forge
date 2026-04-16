"""StudioConnector — integration tests against a real notebook fixture.

Exercises tool dispatch via the Tool.execute callables the orchestrator
would use, with a minimal syllabus seeded under the fixture root.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from forge.connectors.studio import StudioConnector


pytestmark = pytest.mark.skipif(
    shutil.which("rg") is None, reason="ripgrep not installed"
)


_MINIMAL_SYLLABUS = """\
# Course of Study: April–October 2026

## Phase 1: Value Commitment (April–May)

### Core Concept

Values gate everything.

### Evening A Exercises

**Weeks 1–2: Two-value studies.** Work in marker.

**Weeks 3–4: Three-value studies.** Add a mid-tone.

**Weeks 5–6: Full-range graphite, dark-first.** Pencil, darks first.

**Weeks 7–8: Notan thumbnails.** Habit for every session.

### Evening B Application

One rule per session.

### Evening C Master Studies

Kollwitz, Rembrandt.

### Phase 1 Checkpoint

Compare five recent drawings.

## Phase 2: Figure Anatomy (June–July)

### Core Concept

Landmarks.

### Evening A Exercises

**Weeks 1–2: Torso as two boxes.** Draw from imagination.

### Evening B Application

Two-box torso first.

### Evening C Master Studies

Michelangelo.

### Phase 2 Checkpoint

Standing figure from imagination.

## Phase 3: Narrative Composition (August–October)

### Core Concept

Implied story.

### Evening A Exercises

**Weeks 1–3: Thumbnails from masters.** Three per week.

### Evening B Application

Compose at life drawing.

### Evening C Master Studies

Homer, Wyeth.

### Phase 3 Checkpoint

Capstone piece.
"""


@pytest.fixture
def notebook(tmp_path: Path) -> Path:
    """Minimum vault: syllabus at root plus an empty session log directory."""
    root = tmp_path / "vault"
    (root / "Fields" / "Art" / "Session Log").mkdir(parents=True)
    (root / "Fields" / "Art" / "Check-ins").mkdir(parents=True)
    (root / "Artistic Course of Study.md").write_text(_MINIMAL_SYLLABUS)
    return root


@pytest.fixture
async def connector(notebook: Path) -> StudioConnector:
    c = StudioConnector(
        notebook_root=notebook,
        phase_1_start=date(2026, 4, 13),
    )
    await c.setup()
    return c


# ─── Tool surface & health ─────────────────────────────────────────────


async def test_connector_exposes_expected_tools(connector: StudioConnector):
    names = {t.name for t in connector.tools}
    assert names == {
        "studio_current_focus",
        "studio_syllabus_read",
        "studio_list_sessions",
        "studio_get_session",
        "studio_log_session",
        "studio_checkpoint",
        "studio_list_checkins",
    }
    assert all(t.connector_name == "studio" for t in connector.tools)


async def test_health_requires_syllabus_file(notebook: Path):
    # Syllabus present → healthy.
    c = StudioConnector(notebook_root=notebook, phase_1_start=date(2026, 4, 13))
    await c.setup()
    assert await c.health() is True

    # Remove syllabus → connector should report unhealthy so "no data" in
    # current_focus doesn't look like a bug.
    (notebook / "Artistic Course of Study.md").unlink()
    c2 = StudioConnector(notebook_root=notebook, phase_1_start=date(2026, 4, 13))
    await c2.setup()
    assert await c2.health() is False


# ─── Current focus resolution ─────────────────────────────────────────


async def test_current_focus_returns_this_week(connector: StudioConnector):
    result = await connector._current_focus(date="2026-04-16")
    assert result["phase"]["number"] == 1
    assert result["week_in_phase"] == 1
    assert result["evening_a"]["title"] == "Two-value studies"


async def test_current_focus_errors_before_phase_1_start(connector: StudioConnector):
    result = await connector._current_focus(date="2026-04-01")
    assert "error" in result
    assert "before the syllabus start" in result["error"]


async def test_current_focus_rejects_malformed_date(connector: StudioConnector):
    result = await connector._current_focus(date="not-a-date")
    assert "Invalid date" in result["error"]


# ─── Syllabus read ─────────────────────────────────────────────────────


async def test_syllabus_read_returns_full_doc_when_no_phase(connector: StudioConnector):
    result = await connector._syllabus_read()
    assert "Course of Study" in result["title"]
    assert "Phase 1" in result["body"]
    assert "Phase 3" in result["body"]


async def test_syllabus_read_scopes_to_single_phase(connector: StudioConnector):
    result = await connector._syllabus_read(phase=2)
    assert result["phase"] == 2
    assert result["title"] == "Figure Anatomy"
    assert result["evening_a_weeks"][0]["title"] == "Torso as two boxes"


async def test_syllabus_read_rejects_unknown_phase(connector: StudioConnector):
    result = await connector._syllabus_read(phase=42)
    assert "error" in result


async def test_checkpoint_returns_phase_specific_criteria(connector: StudioConnector):
    result = await connector._checkpoint(phase=2)
    assert result["phase"] == 2
    assert "Standing figure from imagination" in result["checkpoint"]


# ─── Session logs ──────────────────────────────────────────────────────


async def test_log_session_writes_file_with_backfilled_phase_and_week(
    connector: StudioConnector, notebook: Path
):
    # Don't pass phase/week — connector should backfill from the schedule.
    result = await connector._log_session(
        title="Two-Value Studies",
        date="2026-04-14",
        evening="A",
        duration_minutes=45,
        materials="brush pen",
        body="10 marker studies of household objects.",
        reflection="Lamp hardest; too many mid-tones.",
    )
    assert result["status"] == "ok"
    assert result["phase"] == 1
    assert result["week"] == 1
    written = (notebook / result["path"]).read_text()
    assert "**Evening:** A" in written
    assert "**Phase:** 1" in written
    assert "**Week:** 1" in written
    assert "## Session" in written
    assert "## Reflection" in written


async def test_log_session_rejects_duplicate_without_overwrite(
    connector: StudioConnector, notebook: Path
):
    await connector._log_session(date="2026-04-14", title="Dup Study", body="x")
    result = await connector._log_session(date="2026-04-14", title="Dup Study", body="y")
    assert "error" in result
    assert "already exists" in result["error"]


async def test_list_sessions_returns_newest_first_with_filtering(
    connector: StudioConnector,
):
    await connector._log_session(
        date="2026-04-14", title="Evening A drill", evening="A", body="b1"
    )
    await connector._log_session(
        date="2026-04-16", title="Life drawing", evening="B", body="b2"
    )
    result = await connector._list_sessions(days=30)
    dates = [e["date"] for e in result["entries"]]
    assert dates == sorted(dates, reverse=True)
    assert result["count"] == 2

    only_a = await connector._list_sessions(days=30, evening="A")
    assert only_a["count"] == 1
    assert only_a["entries"][0]["evening"] == "A"


async def test_get_session_includes_adjacent_images(
    connector: StudioConnector, notebook: Path
):
    await connector._log_session(date="2026-04-14", title="With Photo", body="x")
    # Drop a photo with the same date prefix into the Session Log folder.
    img = notebook / "Fields/Art/Session Log/2026-04-14 photo.jpg"
    img.write_bytes(b"\x00" * 32)
    result = await connector._get_session(
        path="Fields/Art/Session Log/2026-04-14 With Photo.md"
    )
    assert "Fields/Art/Session Log/2026-04-14 photo.jpg" in result["images"]


# ─── Check-ins listing ────────────────────────────────────────────────


async def test_list_checkins_returns_agent_written_files(
    connector: StudioConnector, notebook: Path
):
    checkin = (
        notebook / "Fields/Art/Check-ins/2026-04-20 Weekly Review.md"
    )
    checkin.write_text("# Weekly\n\n**Phase:** 1\n\nYou're drilling well.\n")
    result = await connector._list_checkins(days=30)
    assert result["count"] == 1
    assert result["entries"][0]["title"] == "Weekly Review"
    assert "drilling well" in result["entries"][0]["preview"]
