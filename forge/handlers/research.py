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

    def _snapshot(self) -> set[str]:
        """Relative paths of all files under allowed prefixes."""
        found: set[str] = set()
        for prefix in ALLOWED_WRITE_PREFIXES:
            base = self._root / prefix.rstrip("/")
            if not base.is_dir():
                continue
            for path in base.rglob("*"):
                if path.is_file():
                    found.add(str(path.relative_to(self._root)))
        return found

    async def execute(self, task: Task) -> dict:
        from forge.handlers.research_prompt import build_research_prompt

        before = self._snapshot()
        prompt = build_research_prompt(title=task.title, description=task.description)
        output = await self._claude.run(prompt, str(self._root))
        after = self._snapshot()
        new_files = sorted(after - before)
        return {
            "claude_output": output[:2000],
            "new_files": new_files,
        }
