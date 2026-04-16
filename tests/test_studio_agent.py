"""StudioAgent — tests the triage/execute/verify/deliver lifecycle with
a stubbed Claude runner. The runner is configured to simulate Claude
Code writing a check-in file (or failing), and we confirm the agent's
snapshot detects it and verify/deliver behave accordingly.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from forge.agents import AgentContext
from forge.agents.studio import StudioAgent
from forge.agents.studio_prompt import build_studio_prompt
from forge.models import Task, TaskSource, TaskType


_MINIMAL_SYLLABUS = """\
# Course of Study

## Phase 1: Value Commitment (April–May)

### Core Concept

Values gate everything.

### Evening A Exercises

**Weeks 1–2: Two-value studies.** Work in marker.

### Evening B Application

One rule per session.

### Evening C Master Studies

Kollwitz, Rembrandt.

### Phase 1 Checkpoint

Compare five recent drawings.
"""


class StubClaudeRunner:
    """Captures prompts and simulates writes into the vault."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.side_effect = None  # callable(prompt, work_dir) -> str | Exception

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
    for d in ("Wiki", "Fields/Art/Session Log", "Fields/Art/Check-ins", "Log"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    (tmp_path / "Artistic Course of Study.md").write_text(_MINIMAL_SYLLABUS)
    return tmp_path


@pytest.fixture
def ctx() -> AgentContext:
    return AgentContext(tools=[], store=None, settings=None)


@pytest.fixture
def runner() -> StubClaudeRunner:
    return StubClaudeRunner()


def _make_task(title: str = "Weekly art review", description: str = "Review last week.") -> Task:
    return Task.new(
        task_type=TaskType.RESEARCH,  # any TaskType is fine for the test; type is stringified
        source=TaskSource.CHAT,
        title=title,
        description=description,
    )


def _make_agent(vault: Path, runner: StubClaudeRunner) -> StudioAgent:
    return StudioAgent(
        claude_runner=runner,
        notebook_root=vault,
        phase_1_start=date(2026, 4, 13),
    )


# ─── Triage ────────────────────────────────────────────────────────────


async def test_triage_declines_empty_title(vault: Path, runner, ctx):
    agent = _make_agent(vault, runner)
    task = _make_task(title="   ")
    assert await agent.triage(task, ctx) is False


async def test_triage_declines_when_syllabus_missing(tmp_path: Path, runner, ctx):
    # Vault exists but syllabus file does not.
    (tmp_path / "Fields/Art/Check-ins").mkdir(parents=True)
    agent = StudioAgent(
        claude_runner=runner,
        notebook_root=tmp_path,
        phase_1_start=date(2026, 4, 13),
    )
    task = _make_task()
    assert await agent.triage(task, ctx) is False


async def test_triage_passes_when_syllabus_present(vault: Path, runner, ctx):
    agent = _make_agent(vault, runner)
    task = _make_task()
    assert await agent.triage(task, ctx) is True


# ─── Prompt contents ──────────────────────────────────────────────────


def test_prompt_embeds_current_focus_and_image_instructions():
    prompt = build_studio_prompt(
        title="Review my April 14 session",
        description="Please critique the two-value studies.",
        syllabus_path="Artistic Course of Study.md",
        current_focus={
            "today": "2026-04-16",
            "phase": {"number": 1, "title": "Value Commitment", "date_range": "April–May"},
            "week_in_phase": 1,
            "evening_a": {"title": "Two-value studies", "weeks": "1–2"},
            "core_concept": "Values first.",
        },
        session_log_dir="Fields/Art/Session Log",
        check_in_dir="Fields/Art/Check-ins",
    )
    # Phase context made it into the prompt.
    assert "Phase:** 1 — Value Commitment" in prompt
    assert "Week in phase:** 1" in prompt
    # Image review instructions and the allowlist both present.
    assert "Read tool to load them" in prompt
    assert "Fields/Art/Check-ins" in prompt
    assert "Wiki/" in prompt


# ─── Execute / verify / deliver ────────────────────────────────────────


async def test_execute_detects_check_in_written_by_claude(
    vault: Path, runner: StubClaudeRunner, ctx
):
    # Simulate Claude Code writing the check-in as it runs.
    checkin_rel = "Fields/Art/Check-ins/2026-04-16 Weekly Review.md"

    def side_effect(prompt: str, work_dir: str) -> str:
        (Path(work_dir) / checkin_rel).write_text(
            "# Weekly Review\n\n**Phase:** 1\n**Week:** 1\n\n"
            + "You're committing to true black more often. Keep the marker drills. "
            "Push Evening B rule: darkest dark within 3 minutes." * 3
        )
        return "Wrote 2026-04-16 Weekly Review.md"

    runner.side_effect = side_effect
    agent = _make_agent(vault, runner)
    task = _make_task()

    result = await agent.execute(task, ctx)
    assert result["new_files"] == [checkin_rel]
    assert "Wrote" in result["claude_output"]
    # focus dict was pre-resolved and handed to Claude.
    assert result["focus"]["phase"]["number"] == 1


async def test_verify_accepts_substantial_check_in(vault: Path, runner, ctx):
    agent = _make_agent(vault, runner)
    rel = "Fields/Art/Check-ins/2026-04-16 Weekly Review.md"
    (vault / rel).write_text("# Weekly Review\n\n" + ("Substantial content. " * 50))
    task = _make_task()
    task.handler_data = {"new_files": [rel]}
    assert await agent.verify(task, ctx) is True


async def test_verify_rejects_too_small_output(vault: Path, runner, ctx):
    agent = _make_agent(vault, runner)
    rel = "Fields/Art/Check-ins/2026-04-16 Weekly Review.md"
    (vault / rel).write_text("tiny")
    task = _make_task()
    task.handler_data = {"new_files": [rel]}
    assert await agent.verify(task, ctx) is False


async def test_verify_ignores_files_outside_checkin_dir(vault: Path, runner, ctx):
    agent = _make_agent(vault, runner)
    # A substantial file outside Fields/Art/Check-ins/ shouldn't satisfy verify —
    # the agent is only allowed to produce check-ins here.
    rel = "Wiki/stray.md"
    (vault / "Wiki").mkdir(exist_ok=True)
    (vault / rel).write_text("substantial content " * 100)
    task = _make_task()
    task.handler_data = {"new_files": [rel]}
    assert await agent.verify(task, ctx) is False


async def test_deliver_surfaces_preview_and_word_count(vault: Path, runner, ctx):
    agent = _make_agent(vault, runner)
    rel = "Fields/Art/Check-ins/2026-04-16 Weekly Review.md"
    text = "# Weekly Review\n\n" + " ".join(["word"] * 200)
    (vault / rel).write_text(text)
    task = _make_task()
    task.handler_data = {"new_files": [rel]}
    delivery = await agent.deliver(task, ctx)
    assert delivery["status"] == "delivered"
    assert len(delivery["check_ins"]) == 1
    assert delivery["check_ins"][0]["word_count"] >= 200
    assert delivery["check_ins"][0]["preview"].startswith("# Weekly Review")


async def test_execute_retries_on_transient_runtime_error(
    vault: Path, runner: StubClaudeRunner, ctx
):
    attempts = {"n": 0}

    def side_effect(prompt: str, work_dir: str):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return RuntimeError("flaky CLI")
        (Path(work_dir) / "Fields/Art/Check-ins/2026-04-16 Weekly Review.md").write_text(
            "# Weekly Review\n\n" + ("Substantial content. " * 30)
        )
        return "ok"

    runner.side_effect = side_effect
    agent = _make_agent(vault, runner)
    task = _make_task()
    result = await agent.execute(task, ctx)
    assert attempts["n"] == 2
    assert result["new_files"]
