"""Studio agent — reviews the user's art practice against their syllabus.

Dispatchable from chat (``task_type="studio_review"``). Takes a free-form
title + description describing what kind of review is wanted — weekly
review, phase checkpoint, session critique, next-week plan — and runs
Claude Code inside the notebook vault with syllabus + session context.

The agent writes one check-in markdown file to
``Fields/Art/Check-ins/YYYY-MM-DD <Kind>.md``. It treats adjacent image
files (same date prefix as a session note) as visual evidence and
critiques them directly via Claude Code's image-aware Read tool.

Why Claude Code and not the Anthropic API directly: the agent needs to
Read multiple files (syllabus, every recent session, every adjacent image),
potentially write one, and reason over the combination. That's exactly
what Claude Code is good at — we get the tool loop for free.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path

from forge.agents import AgentContext
from forge.art import (
    CHECK_IN_DIR,
    SESSION_LOG_DIR,
    PhaseSchedule,
    default_phase_schedule,
    parse_syllabus,
    resolve_focus,
)
from forge.claude import ClaudeRunner
from forge.models import Task

logger = logging.getLogger(__name__)

ALLOWED_WRITE_PREFIXES = ("Wiki/", "Fields/", "Log/")
MAX_RETRIES = 2
# Check-ins are typically short reviews, so a 200-byte floor is fine —
# the verify stage just needs to confirm Claude Code actually produced
# a file rather than silently running out.
MIN_FILE_BYTES = 200


class StudioAgent:
    """Art-mentor agent anchored to the Course of Study syllabus."""

    name = "studio"
    task_type = "studio_review"
    stages = ["triage", "execute", "verify", "deliver"]
    connectors = ["notebook", "studio"]

    def __init__(
        self,
        *,
        claude_runner: ClaudeRunner,
        notebook_root: Path,
        phase_1_start: date,
        syllabus_path: str = "Artistic Course of Study.md",
    ) -> None:
        self._claude = claude_runner
        self._root = notebook_root
        self._schedule: PhaseSchedule = default_phase_schedule(phase_1_start)
        self._syllabus_path = syllabus_path

    # ─── Stages ────────────────────────────────────────────────────────

    async def triage(self, task: Task, ctx: AgentContext) -> bool:
        if not task.title or not task.title.strip():
            logger.warning("StudioAgent task %s has empty title, declining", task.id)
            return False
        # If the syllabus file is missing we can't coach anything. Fail early
        # rather than letting Claude Code flail.
        syllabus = self._root / self._syllabus_path
        if not syllabus.is_file():
            logger.warning(
                "StudioAgent declining task %s — syllabus not found at %s",
                task.id,
                syllabus,
            )
            return False
        return True

    async def execute(self, task: Task, ctx: AgentContext) -> dict:
        from forge.agents.studio_prompt import build_studio_prompt

        focus_dict = self._resolve_focus_dict()
        before = self._checkin_snapshot()

        retry_context: str | None = None
        output = ""
        for attempt in range(MAX_RETRIES + 1):
            prompt = build_studio_prompt(
                title=task.title,
                description=task.description,
                syllabus_path=self._syllabus_path,
                current_focus=focus_dict,
                session_log_dir=SESSION_LOG_DIR,
                check_in_dir=CHECK_IN_DIR,
                retry_context=retry_context,
            )
            try:
                output = await self._claude.run(prompt, str(self._root))
                break
            except (TimeoutError, RuntimeError) as exc:
                logger.warning("StudioAgent attempt %d failed: %s", attempt + 1, exc)
                retry_context = f"Attempt {attempt + 1} failed: {exc}"
                if attempt == MAX_RETRIES:
                    raise

        after = self._checkin_snapshot()
        new_files = sorted(after - before)
        return {
            "claude_output": output[:2000],
            "new_files": new_files,
            "focus": focus_dict,
        }

    async def verify(self, task: Task, ctx: AgentContext) -> bool:
        new_files = task.handler_data.get("new_files", [])
        for rel in new_files:
            if not rel.startswith(CHECK_IN_DIR + "/"):
                continue
            path = self._root / rel
            if not path.is_file():
                continue
            if path.stat().st_size < MIN_FILE_BYTES:
                continue
            return True
        return False

    async def deliver(self, task: Task, ctx: AgentContext) -> dict:
        new_files = task.handler_data.get("new_files", [])
        summaries: list[dict] = []
        for rel in new_files:
            if not rel.startswith(CHECK_IN_DIR + "/"):
                continue
            path = self._root / rel
            if not path.is_file():
                continue
            text = path.read_text()
            summaries.append(
                {
                    "path": rel,
                    "word_count": len(text.split()),
                    "preview": text[:600],
                }
            )
        return {
            "status": "delivered",
            "check_ins": summaries,
            "notebook_commit_pending": True,
        }

    # ─── Helpers ───────────────────────────────────────────────────────

    def _resolve_focus_dict(self) -> dict | None:
        """Resolve the current focus payload (or None if before Phase 1 start)."""
        try:
            body = (self._root / self._syllabus_path).read_text()
        except OSError:
            return None
        try:
            syllabus = parse_syllabus(body)
        except Exception:
            logger.exception("StudioAgent failed to parse syllabus")
            return None
        today = datetime.now(tz=timezone.utc).date()
        focus = resolve_focus(syllabus, self._schedule, today)
        return focus.to_dict() if focus is not None else None

    def _checkin_snapshot(self) -> set[str]:
        """Relative paths of files currently in the Check-ins directory.

        Used by execute() to detect which files Claude Code created. We scope
        the snapshot tightly to ``Fields/Art/Check-ins/`` so we don't get
        noise from unrelated writes.
        """
        found: set[str] = set()
        base = self._root / CHECK_IN_DIR
        if not base.is_dir():
            return found
        for path in base.rglob("*"):
            if path.is_file():
                found.add(str(path.relative_to(self._root)))
        return found
