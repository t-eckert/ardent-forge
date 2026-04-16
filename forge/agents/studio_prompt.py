"""Prompt builder for the studio (art-mentor) task handler.

Keeps the agent file itself lean and makes the prompt easy to iterate on
without touching Python code. The prompt gives Claude Code enough context
to coach the user against the correct week of their syllabus, including
reading adjacent image files for visual critique.
"""

from __future__ import annotations


def build_studio_prompt(
    *,
    title: str,
    description: str,
    syllabus_path: str,
    current_focus: dict | None,
    session_log_dir: str,
    check_in_dir: str,
    retry_context: str | None = None,
) -> str:
    """Compose the task prompt for the StudioAgent.

    ``current_focus`` is the pre-resolved payload from ``studio_current_focus``
    so Claude Code doesn't have to derive it. Passing it in keeps the Claude
    turn short and grounded.
    """
    focus_section = _render_focus(current_focus)
    parts = [
        f"# Art Mentor Task: {title}",
        f"\n## Request\n{description}",
        focus_section,
        "\n## What to do",
        (
            "You are the user's art-mentor agent. The user is six months into a "
            "self-directed study plan with three phases (value commitment, figure "
            "anatomy, narrative composition). Your job is to give them grounded, "
            "phase-aware feedback and coordination — not generic art advice."
        ),
        "",
        "**Start by reading:**",
        f"- The syllabus at `{syllabus_path}` (full document).",
        (
            f"- Recent session logs in `{session_log_dir}/`. Sessions are named "
            "`YYYY-MM-DD <Title>.md` with bold-field metadata (Evening, Phase, "
            "Week, Duration, Materials, Focus) and freeform body."
        ),
        (
            "- Adjacent image files in the same folder with the same date prefix "
            "(e.g. `2026-04-14 *.jpg`). **Use the Read tool to load them** — Read "
            "supports images and passes them to you as visual content. When images "
            "are present, include visual critique grounded in what you see, not "
            "generic commentary. Cite specifics: what you see in the piece, how it "
            "compares to the phase's core concept, where to push next."
        ),
        (
            f"- Past check-ins in `{check_in_dir}/`. Use them to avoid repeating "
            "yourself and to track the user's trajectory week over week."
        ),
        "",
        "**Then produce a check-in note:**",
        (
            f"- Write a single markdown file to `{check_in_dir}/YYYY-MM-DD <Kind>.md` "
            "(kind = \"Weekly Review\", \"Phase Checkpoint\", \"Session Critique\", "
            "\"Week Plan\", etc. — pick the one that fits the request)."
        ),
        (
            "- Lead with `**Phase:** N`, `**Week:** N`, `**Kind:** <kind>`, "
            "`**Daily Log:** [[YYYY-MM-DD]]` metadata. Mirror the session-log style."
        ),
        (
            "- Keep it tight and direct — you're a mentor, not a cheerleader. Name "
            "what's working, name what's drifting, and give one or two specific "
            "next actions. Reference the current phase's drill exercise by name."
        ),
        (
            "- If the task asks for a plan (e.g. \"plan next week\"), lay it out as "
            "Evening A, B, C with concrete prompts the user can act on. Respect the "
            "\"one rule per session\" principle from Phase 1."
        ),
        "",
        "**Critical rules:**",
        (
            "- Only write inside the allowed prefixes: `Wiki/`, `Fields/`, `Log/`. "
            f"Check-ins belong in `{check_in_dir}/`; never overwrite existing "
            "session logs."
        ),
        (
            "- Do not commit. Do not create a git branch. Just write the file."
        ),
        (
            "- Wrap any artist or book name that might have a notebook page as a "
            "wikilink, e.g. [[Käthe Kollwitz]], [[Imaginative Realism]]. If you "
            "don't know whether it exists, wikilink it anyway — Obsidian handles "
            "unresolved links gracefully."
        ),
        (
            "- If an image looks visibly wrong (rotated, blurry, too dark to judge), "
            "say so explicitly rather than inventing observations."
        ),
    ]
    if retry_context:
        parts.append(f"\n## Previous Attempt\n{retry_context}")
    return "\n".join(parts)


def _render_focus(focus: dict | None) -> str:
    if not focus:
        return "\n## Current Focus\n(Could not resolve — the date is before the syllabus start.)"
    phase = focus.get("phase", {})
    evening_a = focus.get("evening_a", {})
    lines = [
        "\n## Current Focus",
        f"- **Today:** {focus.get('today', '')}",
        f"- **Phase:** {phase.get('number', '?')} — {phase.get('title', '')} ({phase.get('date_range', '')})",
        f"- **Week in phase:** {focus.get('week_in_phase', '?')}",
    ]
    if evening_a.get("title"):
        lines.append(
            f"- **Evening A drill ({evening_a.get('weeks', '')}):** {evening_a['title']}"
        )
    if focus.get("core_concept"):
        lines.append("")
        lines.append("**Phase core concept (excerpt):**")
        lines.append(focus["core_concept"][:400] + ("…" if len(focus["core_concept"]) > 400 else ""))
    return "\n".join(lines)
