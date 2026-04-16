"""Art study domain — syllabus parsing, session logs, and check-in writes.

Kept separate from forge/connectors/studio.py so the parsers and writers
are testable without the async Connector shell. The connector and the
StudioAgent are both thin layers over this.
"""

from forge.art.sessions import (
    CHECK_IN_DIR,
    SESSION_LOG_DIR,
    SessionEntry,
    StudioSessions,
    parse_session_markdown,
    render_check_in_template,
    render_session_template,
)
from forge.art.syllabus import (
    CurrentFocus,
    Phase,
    PhaseSchedule,
    Syllabus,
    WeekBlock,
    default_phase_schedule,
    parse_syllabus,
    resolve_focus,
)

__all__ = [
    "CHECK_IN_DIR",
    "CurrentFocus",
    "Phase",
    "PhaseSchedule",
    "SESSION_LOG_DIR",
    "SessionEntry",
    "StudioSessions",
    "Syllabus",
    "WeekBlock",
    "default_phase_schedule",
    "parse_session_markdown",
    "parse_syllabus",
    "render_check_in_template",
    "render_session_template",
    "resolve_focus",
]
