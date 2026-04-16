"""Domain tests for forge.art — syllabus parser, date→phase/week resolver,
and session/check-in parsers and renderers. No Connector, no Claude Code.
"""

from __future__ import annotations

from datetime import date

import pytest

from forge.art import (
    default_phase_schedule,
    parse_session_markdown,
    parse_syllabus,
    render_check_in_template,
    render_session_template,
    resolve_focus,
)
from forge.art.syllabus import PhaseSchedule


SAMPLE_SYLLABUS = """\
# Course of Study: April–October 2026

**Three priorities:** Value commitment · Figure anatomy · Narrative composition

## How to Use This Syllabus

Each phase runs roughly two months.

## Phase 1: Value Commitment (April–May)

This is first because values gate everything else.

### Core Concept

You're not adding darks — you're learning to see as light and shadow.

### Evening A Exercises

**Weeks 1–2: Two-value studies.** Work in marker. Two values only.

**Weeks 3–4: Three-value studies.** Add a mid-tone.

**Weeks 5–6: Full-range graphite, dark-first.** Return to pencil.

**Weeks 7–8: Notan thumbnails.** Habit for every session.

### Evening B Application

Apply one rule per session at life drawing.

### Evening C Master Studies

Study Kollwitz and Rembrandt.

### Phase 1 Checkpoint

Compare five drawings before and after.

## Phase 2: Figure Anatomy (June–July)

### Core Concept

Anatomy is landmark recognition, not memorization.

### Evening A Exercises

**Weeks 1–2: Torso as two boxes.**

**Weeks 3–4: Landmark mapping.**

**Weeks 5–6: Hands and feet.**

**Weeks 7–8: Standing poses.**

### Evening B Application

Two-box torso before every life drawing pose.

### Evening C Master Studies

Michelangelo, Bridgman, Loomis.

### Phase 2 Checkpoint

Standing figure from imagination.

## Phase 3: Narrative Composition (August–October)

### Core Concept

Narrative is a moment that implies before and after.

### Evening A Exercises

**Weeks 1–3: Compositional thumbnails from masters.**

**Weeks 4–6: Figure-in-environment studies.**

**Weeks 7–9: Narrative watercolor sketches.**

**Weeks 10–12: Capstone piece.**

### Evening B Application

Composition at life drawing.

### Evening C Master Studies

Homer, Wyeth, Gurney, Hopper.

### Phase 3 Checkpoint

Capstone piece shown alongside phase 1 and 2 work.

## Ongoing Habits to Carry Through All Phases

Notan thumbnails. Sketchbook. Monthly comparison.

## Recommended Book List (Prioritized)

1. Carlson
2. Loomis

## A Note on Medium

Drawing first, then watercolor.
"""


# ─── Syllabus parser ───────────────────────────────────────────────────


def test_parse_syllabus_extracts_all_three_phases():
    syl = parse_syllabus(SAMPLE_SYLLABUS)
    assert syl.title == "Course of Study: April–October 2026"
    assert [p.number for p in syl.phases] == [1, 2, 3]
    assert [p.title for p in syl.phases] == [
        "Value Commitment",
        "Figure Anatomy",
        "Narrative Composition",
    ]


def test_parse_syllabus_pulls_week_blocks_out_of_evening_a():
    syl = parse_syllabus(SAMPLE_SYLLABUS)
    phase1_blocks = syl.phase(1).evening_a_weeks
    assert len(phase1_blocks) == 4
    assert phase1_blocks[0].first_week == 1
    assert phase1_blocks[0].last_week == 2
    assert phase1_blocks[0].title == "Two-value studies"
    # Week titles end without a trailing period (parser strips it for readability).
    assert not phase1_blocks[0].title.endswith(".")


def test_parse_syllabus_captures_phase_3_twelve_weeks():
    syl = parse_syllabus(SAMPLE_SYLLABUS)
    blocks = syl.phase(3).evening_a_weeks
    assert blocks[-1].first_week == 10
    assert blocks[-1].last_week == 12


def test_parse_syllabus_separates_checkpoint_from_evening_sections():
    syl = parse_syllabus(SAMPLE_SYLLABUS)
    p1 = syl.phase(1)
    assert "Compare five drawings" in p1.checkpoint
    # Checkpoint body must not leak back into Evening C.
    assert "Compare five drawings" not in p1.evening_c


def test_parse_syllabus_captures_post_phase_sections():
    syl = parse_syllabus(SAMPLE_SYLLABUS)
    assert "Notan thumbnails" in syl.ongoing_habits
    assert "Carlson" in syl.book_list
    assert "Drawing first" in syl.medium_note


# ─── Date → phase/week resolver ────────────────────────────────────────


def test_default_schedule_spans_eight_plus_eight_plus_twelve_weeks():
    sched = default_phase_schedule(date(2026, 4, 13))
    assert [a[0] for a in sched.anchors] == [1, 2, 3]
    # Phase 2 starts exactly 8 weeks after phase 1.
    assert sched.anchors[1][1] == date(2026, 6, 8)
    # Phase 3 starts 16 weeks after phase 1.
    assert sched.anchors[2][1] == date(2026, 8, 3)


def test_resolve_focus_returns_none_before_start():
    syl = parse_syllabus(SAMPLE_SYLLABUS)
    sched = default_phase_schedule(date(2026, 4, 13))
    assert resolve_focus(syl, sched, date(2026, 4, 1)) is None


@pytest.mark.parametrize(
    "today,expected_phase,expected_week,expected_block_title",
    [
        (date(2026, 4, 13), 1, 1, "Two-value studies"),
        (date(2026, 4, 19), 1, 1, "Two-value studies"),  # end of week 1
        (date(2026, 4, 20), 1, 2, "Two-value studies"),  # start of week 2
        (date(2026, 5, 1), 1, 3, "Three-value studies"),
        (date(2026, 5, 30), 1, 7, "Notan thumbnails"),
        (date(2026, 6, 8), 2, 1, "Torso as two boxes"),
        (date(2026, 7, 6), 2, 5, "Hands and feet"),
        (date(2026, 8, 3), 3, 1, "Compositional thumbnails from masters"),
        (date(2026, 10, 12), 3, 11, "Capstone piece"),
    ],
)
def test_resolve_focus_maps_dates_to_correct_slice(
    today, expected_phase, expected_week, expected_block_title
):
    syl = parse_syllabus(SAMPLE_SYLLABUS)
    sched = default_phase_schedule(date(2026, 4, 13))
    focus = resolve_focus(syl, sched, today)
    assert focus is not None
    assert focus.phase_number == expected_phase
    assert focus.week_in_phase == expected_week
    assert focus.evening_a_title == expected_block_title


def test_resolve_focus_past_end_clamps_to_last_phase_final_week():
    syl = parse_syllabus(SAMPLE_SYLLABUS)
    sched = default_phase_schedule(date(2026, 4, 13))
    focus = resolve_focus(syl, sched, date(2027, 1, 1))
    assert focus is not None
    assert focus.phase_number == 3
    assert focus.week_in_phase == 12


def test_resolve_focus_includes_checkpoint_for_agent_context():
    syl = parse_syllabus(SAMPLE_SYLLABUS)
    sched = default_phase_schedule(date(2026, 4, 13))
    focus = resolve_focus(syl, sched, date(2026, 4, 20))
    assert focus is not None
    # The checkpoint text is handed to the agent so it can reason about what
    # "ready for the next phase" actually means this week.
    assert "Compare" in focus.checkpoint


def test_phase_schedule_handles_empty_anchors():
    empty = PhaseSchedule(anchors=[])
    assert empty.resolve(date(2026, 5, 1)) is None


# ─── Session parser + renderer ─────────────────────────────────────────


def test_parse_session_extracts_metadata_and_keeps_raw():
    body = (
        "# Tue 14 April 2026\n"
        "\n"
        "**Evening:** A\n"
        "**Phase:** 1\n"
        "**Week:** 1\n"
        "**Duration:** 45 minutes\n"
        "**Materials:** brush pen, cheap copy paper\n"
        "**Focus:** [[Two-Value Studies]]\n"
        "**Daily Log:** [[2026-04-14]]\n"
        "\n"
        "## Session\n"
        "\n"
        "freeform content here.\n"
    )
    entry = parse_session_markdown(
        "Fields/Art/Session Log/2026-04-14 Two-Value Studies.md",
        body,
        images=["Fields/Art/Session Log/2026-04-14 page1.jpg"],
    )
    assert entry.date == date(2026, 4, 14)
    assert entry.title == "Two-Value Studies"
    assert entry.evening == "A"
    assert entry.phase == 1
    assert entry.week == 1
    assert entry.duration_minutes == 45
    assert entry.materials == "brush pen, cheap copy paper"
    # Wikilink stripped so the string is useful for display.
    assert entry.focus == "Two-Value Studies"
    assert entry.images == ["Fields/Art/Session Log/2026-04-14 page1.jpg"]
    assert entry.raw == body


def test_parse_session_tolerates_missing_fields():
    body = "# Sat 12 April 2026\n\nfreeform note.\n"
    entry = parse_session_markdown(
        "Fields/Art/Session Log/2026-04-12 Quick sketch.md", body
    )
    assert entry.date == date(2026, 4, 12)
    assert entry.title == "Quick sketch"
    assert entry.evening is None
    assert entry.phase is None
    assert entry.duration_minutes is None


def test_render_session_template_includes_all_supplied_fields():
    text = render_session_template(
        entry_date=date(2026, 4, 14),
        evening="A",
        phase=1,
        week=1,
        duration_minutes=45,
        materials="brush pen",
        focus="Two-Value Studies",
        body="10 marker studies of household objects.",
        reflection="Lamp was hardest — too many mid-tones.",
    )
    assert "# Tue 14 April 2026" in text
    assert "**Evening:** A" in text
    assert "**Phase:** 1" in text
    assert "**Week:** 1" in text
    assert "**Daily Log:** [[2026-04-14]]" in text
    assert "## Session" in text
    assert "## Reflection" in text
    assert "Lamp was hardest" in text


def test_render_check_in_template_sets_kind_and_metadata():
    body = "## Value commitment\n\nYou're starting to hit true black.\n"
    text = render_check_in_template(
        entry_date=date(2026, 4, 20),
        kind="Weekly Review",
        phase=1,
        week=2,
        body=body,
    )
    assert text.startswith("# Mon 20 April 2026 — Weekly Review")
    assert "**Phase:** 1" in text
    assert "**Week:** 2" in text
    assert "**Kind:** Weekly Review" in text
    assert "You're starting to hit true black." in text
