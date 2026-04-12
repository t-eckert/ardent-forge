"""Research task handler — runs Claude Code in the Notebook vault."""

import logging
from pathlib import Path

from forge.claude import ClaudeRunner
from forge.models import Task

logger = logging.getLogger(__name__)

ALLOWED_WRITE_PREFIXES = ("Wiki/", "Fields/", "Log/")
MAX_RETRIES = 2
MIN_FILE_BYTES = 200


class ResearchHandler:
    task_type: str = "research"

    def __init__(
        self,
        claude_runner: ClaudeRunner,
        notebook_root: Path,
    ):
        self._claude = claude_runner
        self._root = notebook_root

    async def triage(self, task: Task) -> bool:
        if not task.title or not task.title.strip():
            logger.warning(f"Task {task.id} has empty title, declining")
            return False
        return True
