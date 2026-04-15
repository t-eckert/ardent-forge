"""Research agent — runs Claude Code in the Notebook vault."""

import logging
from pathlib import Path

from forge.agents import AgentContext
from forge.claude import ClaudeRunner
from forge.models import Task

logger = logging.getLogger(__name__)

ALLOWED_WRITE_PREFIXES = ("Wiki/", "Fields/", "Log/")
MAX_RETRIES = 2
MIN_FILE_BYTES = 200


class ResearchAgent:
    name = "research"
    task_type = "research"
    stages = ["triage", "execute", "verify", "deliver"]
    connectors = ["notebook", "web_search"]

    def __init__(
        self,
        claude_runner: ClaudeRunner,
        notebook_root: Path,
    ):
        self._claude = claude_runner
        self._root = notebook_root

    async def triage(self, task: Task, ctx: AgentContext) -> bool:
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

    async def execute(self, task: Task, ctx: AgentContext) -> dict:
        from forge.agents.research_prompt import build_research_prompt

        before = self._snapshot()
        retry_context: str | None = None
        output = ""

        for attempt in range(MAX_RETRIES + 1):
            prompt = build_research_prompt(
                title=task.title,
                description=task.description,
                retry_context=retry_context,
            )
            try:
                output = await self._claude.run(prompt, str(self._root))
                break
            except (TimeoutError, RuntimeError) as e:
                logger.warning(f"Research attempt {attempt + 1} failed: {e}")
                retry_context = f"Attempt {attempt + 1} failed: {e}"
                if attempt == MAX_RETRIES:
                    raise

        after = self._snapshot()
        new_files = sorted(after - before)
        return {
            "claude_output": output[:2000],
            "new_files": new_files,
        }

    async def verify(self, task: Task, ctx: AgentContext) -> bool:
        new_files = task.handler_data.get("new_files", [])
        for rel in new_files:
            if not any(rel.startswith(prefix) for prefix in ALLOWED_WRITE_PREFIXES):
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
            if not any(rel.startswith(prefix) for prefix in ALLOWED_WRITE_PREFIXES):
                continue
            path = self._root / rel
            if not path.is_file():
                continue
            text = path.read_text()
            summaries.append(
                {
                    "path": rel,
                    "word_count": len(text.split()),
                    "preview": text[:500],
                }
            )
        return {
            "status": "delivered",
            "files": summaries,
            "notebook_commit_pending": True,
        }
