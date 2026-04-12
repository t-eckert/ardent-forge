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


@pytest.mark.asyncio
async def test_execute_detects_new_file(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    def write_file(_prompt: str, _work_dir: str) -> str:
        (vault / "Wiki" / "OpenClaw.md").write_text("# OpenClaw\n\n" + "x" * 300)
        return "done"

    runner.side_effect = write_file
    task = _research_task()
    result = await handler.execute(task)

    assert result["new_files"] == ["Wiki/OpenClaw.md"]
    assert result["claude_output"] == "done"


@pytest.mark.asyncio
async def test_execute_ignores_pre_existing_files(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    (vault / "Wiki" / "Existing.md").write_text("pre-existing content")

    def write_file(_prompt: str, _work_dir: str) -> str:
        (vault / "Wiki" / "New.md").write_text("new content" * 50)
        return ""

    runner.side_effect = write_file
    task = _research_task()
    result = await handler.execute(task)

    assert result["new_files"] == ["Wiki/New.md"]


@pytest.mark.asyncio
async def test_execute_passes_notebook_root_as_work_dir(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    task = _research_task()
    await handler.execute(task)
    assert len(runner.calls) == 1
    _prompt, work_dir = runner.calls[0]
    assert work_dir == str(vault)


@pytest.mark.asyncio
async def test_execute_ignores_files_outside_allowed_prefixes(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    def write_elsewhere(_prompt: str, _work_dir: str) -> str:
        (vault / "People" / "Foo.md").write_text("oops")
        return ""

    runner.side_effect = write_elsewhere
    task = _research_task()
    result = await handler.execute(task)
    # Snapshot is limited to allowed prefixes — a write to People/ is invisible
    assert result["new_files"] == []


@pytest.mark.asyncio
async def test_execute_truncates_claude_output(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    def huge_output(_prompt: str, _work_dir: str) -> str:
        return "x" * 5000

    runner.side_effect = huge_output
    task = _research_task()
    result = await handler.execute(task)
    assert len(result["claude_output"]) == 2000
