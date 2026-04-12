from pathlib import Path

import pytest

from forge.handlers.research import ResearchHandler
from forge.models import Task, TaskSource, TaskType


class StubClaudeRunner:
    """Minimal stand-in for ClaudeRunner used by handler tests."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.side_effect = None  # Callable[[prompt, work_dir], str] or Exception class iter

    async def run(self, prompt: str, work_dir: str) -> str:
        self.calls.append((prompt, work_dir))
        if self.side_effect is not None:
            result = self.side_effect(prompt, work_dir)
            if isinstance(result, Exception):
                raise result
            return result
        return ""


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    for d in ("Wiki", "Fields", "Log", "People", "+Templates"):
        (tmp_path / d).mkdir()
    (tmp_path / "CLAUDE.md").write_text("# Notebook conventions")
    return tmp_path


@pytest.fixture
def runner() -> StubClaudeRunner:
    return StubClaudeRunner()


@pytest.fixture
def handler(vault: Path, runner: StubClaudeRunner) -> ResearchHandler:
    return ResearchHandler(claude_runner=runner, notebook_root=vault)


def _research_task(title: str = "OpenClaw Use Cases", description: str = "Collect blog posts.") -> Task:
    return Task.new(
        task_type=TaskType.RESEARCH,
        source=TaskSource.CHAT,
        title=title,
        description=description,
    )


def test_handler_task_type(handler: ResearchHandler):
    assert handler.task_type == "research"


@pytest.mark.asyncio
async def test_triage_accepts_non_empty_title(handler: ResearchHandler):
    task = _research_task(title="Real title")
    assert await handler.triage(task) is True


@pytest.mark.asyncio
async def test_triage_declines_empty_title(handler: ResearchHandler):
    task = _research_task(title="")
    assert await handler.triage(task) is False


@pytest.mark.asyncio
async def test_triage_declines_whitespace_title(handler: ResearchHandler):
    task = _research_task(title="   ")
    assert await handler.triage(task) is False
