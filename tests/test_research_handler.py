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


@pytest.mark.asyncio
async def test_execute_retries_on_timeout(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    call_count = {"n": 0}

    def flaky(_prompt: str, _work_dir: str) -> str:
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise TimeoutError("first try")
        (vault / "Wiki" / "Later.md").write_text("x" * 300)
        return "ok"

    runner.side_effect = flaky
    task = _research_task()
    result = await handler.execute(task)
    assert call_count["n"] == 2
    assert result["new_files"] == ["Wiki/Later.md"]


@pytest.mark.asyncio
async def test_execute_retries_on_runtime_error(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    call_count = {"n": 0}

    def flaky(_prompt: str, _work_dir: str) -> str:
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise RuntimeError("boom")
        (vault / "Wiki" / "Finally.md").write_text("x" * 300)
        return "ok"

    runner.side_effect = flaky
    task = _research_task()
    result = await handler.execute(task)
    assert call_count["n"] == 3
    assert result["new_files"] == ["Wiki/Finally.md"]


@pytest.mark.asyncio
async def test_execute_raises_after_max_retries(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    def always_fail(_prompt: str, _work_dir: str) -> str:
        raise TimeoutError("forever")

    runner.side_effect = always_fail
    task = _research_task()
    with pytest.raises(TimeoutError):
        await handler.execute(task)


@pytest.mark.asyncio
async def test_execute_retry_passes_context_to_prompt(handler: ResearchHandler, vault: Path, runner: StubClaudeRunner):
    prompts: list[str] = []
    call_count = {"n": 0}

    def capture(prompt: str, _work_dir: str) -> str:
        prompts.append(prompt)
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise RuntimeError("first failure message")
        (vault / "Wiki" / "Ok.md").write_text("x" * 300)
        return "ok"

    runner.side_effect = capture
    task = _research_task()
    await handler.execute(task)
    assert "Previous Attempt" in prompts[1]
    assert "first failure message" in prompts[1]


@pytest.mark.asyncio
async def test_verify_true_when_new_file_in_allowed_dir_with_content(handler: ResearchHandler, vault: Path):
    (vault / "Wiki" / "Ok.md").write_text("x" * 300)
    task = _research_task()
    task.handler_data = {"new_files": ["Wiki/Ok.md"]}
    assert await handler.verify(task) is True


@pytest.mark.asyncio
async def test_verify_false_when_no_new_files(handler: ResearchHandler):
    task = _research_task()
    task.handler_data = {"new_files": []}
    assert await handler.verify(task) is False


@pytest.mark.asyncio
async def test_verify_false_when_file_too_small(handler: ResearchHandler, vault: Path):
    (vault / "Wiki" / "Stub.md").write_text("tiny")
    task = _research_task()
    task.handler_data = {"new_files": ["Wiki/Stub.md"]}
    assert await handler.verify(task) is False


@pytest.mark.asyncio
async def test_verify_false_when_only_file_is_outside_allowlist(handler: ResearchHandler, vault: Path):
    (vault / "People" / "Foo.md").write_text("x" * 300)
    task = _research_task()
    task.handler_data = {"new_files": ["People/Foo.md"]}
    assert await handler.verify(task) is False


@pytest.mark.asyncio
async def test_verify_true_when_mixed_files_include_valid_one(handler: ResearchHandler, vault: Path):
    (vault / "People" / "Foo.md").write_text("x" * 300)
    (vault / "Fields").mkdir(exist_ok=True)
    (vault / "Fields" / "Redpanda.md").write_text("x" * 300)
    task = _research_task()
    task.handler_data = {"new_files": ["People/Foo.md", "Fields/Redpanda.md"]}
    assert await handler.verify(task) is True


@pytest.mark.asyncio
async def test_verify_false_when_file_missing_from_disk(handler: ResearchHandler):
    task = _research_task()
    task.handler_data = {"new_files": ["Wiki/Vanished.md"]}
    assert await handler.verify(task) is False
