import pytest

from forge.claude import build_prompt, ClaudeRunner


def test_build_prompt_basic():
    prompt = build_prompt(
        title="Fix the login bug",
        description="Users can't log in when password has special chars",
        repo="t-eckert/myapp",
    )
    assert "Fix the login bug" in prompt
    assert "special chars" in prompt
    assert "t-eckert/myapp" in prompt


def test_build_prompt_with_analysis():
    prompt = build_prompt(
        title="Add feature",
        description="New feature needed",
        repo="t-eckert/myapp",
        analysis="The codebase uses FastAPI with SQLAlchemy",
    )
    assert "FastAPI with SQLAlchemy" in prompt


def test_build_prompt_with_retry_context():
    prompt = build_prompt(
        title="Fix bug",
        description="Bug description",
        repo="t-eckert/myapp",
        retry_context="Previous attempt failed: ImportError in module X",
    )
    assert "Previous attempt" in prompt
    assert "ImportError" in prompt


def test_claude_runner_init():
    runner = ClaudeRunner(model="opus", timeout=120)
    assert runner._model == "opus"
    assert runner._timeout == 120


def test_claude_runner_default_model():
    runner = ClaudeRunner()
    assert runner._model == "sonnet"
