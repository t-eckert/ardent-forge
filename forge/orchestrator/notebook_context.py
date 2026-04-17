"""Builds the notebook context block for Forge's system prompt.

Gives Forge ambient awareness of the notebook: its structure, today's log,
and recent activity — so it can proactively use notebook tools without being
explicitly asked.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forge.notebook.reader import NotebookReader

logger = logging.getLogger(__name__)

# Top-level sections to summarise in the structure overview.
_SECTIONS = ("Log", "Wiki", "Fields", "Projects", "People", "Collections")


def _today_log(reader: "NotebookReader") -> str | None:
    """Read today's daily log, if it exists."""
    today = datetime.now().strftime("%Y-%m-%d")
    path = f"Log/{today}.md"
    if not reader.exists(path):
        return None
    try:
        content = reader.read(path)
        # Truncate very long logs to keep the prompt reasonable.
        if len(content) > 3000:
            content = content[:3000] + "\n\n…(truncated)"
        return content
    except Exception:
        logger.debug("Could not read today's log", exc_info=True)
        return None


def _section_summary(reader: "NotebookReader") -> str:
    """One-line summary of each top-level section."""
    lines: list[str] = []
    for section in _SECTIONS:
        if not reader.exists(section):
            continue
        try:
            entries = reader.list_dir(section)
        except Exception:
            continue
        # Count files vs subdirs
        count = len(entries)
        lines.append(f"- **{section}/**: {count} entries")
    return "\n".join(lines)


def _recent_activity(reader: "NotebookReader") -> str:
    """Most recently modified files across key sections."""
    lines: list[str] = []
    try:
        recent = reader.recent("", limit=10)
    except Exception:
        return ""
    for path, mtime in recent:
        ts = datetime.fromtimestamp(mtime).strftime("%b %d")
        lines.append(f"- {path} ({ts})")
    return "\n".join(lines)


def build_notebook_context(reader: "NotebookReader") -> str:
    """Assemble the notebook context block for the system prompt."""
    parts = [
        "## Notebook",
        "",
        "Thomas's Obsidian notebook is available to you. It is an 8-year personal "
        "knowledge base with daily logs, wiki entries, project notes, people files, "
        "and field notes across all areas of his life.",
        "",
        "### Structure",
        _section_summary(reader),
        "",
        "Key sections:",
        "- **Log/**: Daily logs (YYYY-MM-DD.md). Task notation: `[x]` done, `[>]` deferred, `[<]` paused, `[~]` partial, `[!]` dropped.",
        "- **Fields/**: Long-running life areas (no end state): Art, Career, Health, Finances, Home, etc.",
        "- **Projects/**: Completable work with defined end states. Subdirs: +Ideas, +Paused, +Completed, +Archived.",
        "- **Wiki/**: Transferable knowledge — concepts, reference, book/article notes.",
        "- **People/**: One file per person. Referenced from logs via `[[Name]]`.",
        "- **Collections/**: Curated lists (Books, Places, TV and Film).",
        "",
        "### How to use the notebook",
        "- Use `notebook_search` to find what Thomas has written about a topic.",
        "- Use `notebook_read` or `notebook_log` to read specific notes.",
        "- Use `notebook_recent` to see what's been active lately.",
        "- Use `notebook_resolve_wikilink` to find where a `[[Name]]` lives.",
        "- When Thomas mentions a person, project, or topic, check the notebook — you'll often find relevant context.",
        "- When writing notes, follow the section semantics: Fields for ongoing areas, Projects for completable work, Wiki for transferable knowledge.",
    ]

    today_content = _today_log(reader)
    if today_content:
        parts.extend([
            "",
            "### Today's log",
            f"```markdown",
            today_content,
            "```",
        ])
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        parts.extend([
            "",
            f"### Today's log",
            f"No log entry yet for {today}.",
        ])

    recent = _recent_activity(reader)
    if recent:
        parts.extend([
            "",
            "### Recent activity",
            recent,
        ])

    return "\n".join(parts)
