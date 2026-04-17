"""Tests for the notebook context block injected into Forge's system prompt."""

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from forge.notebook.reader import NotebookReader
from forge.orchestrator.notebook_context import build_notebook_context


pytestmark = pytest.mark.skipif(
    shutil.which("rg") is None, reason="ripgrep not installed"
)


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    for d in ("Wiki", "Fields", "Log", "People", "Projects", "Collections"):
        (tmp_path / d).mkdir()
    (tmp_path / "Wiki" / "Svelte 5.md").write_text("# Svelte 5\n")
    (tmp_path / "People" / "Alice.md").write_text("# Alice\n")
    return tmp_path


@pytest.fixture
def reader(vault: Path) -> NotebookReader:
    return NotebookReader(vault)


def test_includes_structure_summary(reader: NotebookReader):
    ctx = build_notebook_context(reader)
    assert "## Notebook" in ctx
    assert "**Wiki/**" in ctx
    assert "**People/**" in ctx


def test_includes_todays_log_when_present(vault: Path, reader: NotebookReader):
    today = datetime.now().strftime("%Y-%m-%d")
    (vault / "Log" / f"{today}.md").write_text("- [x] Built notebook context\n")
    ctx = build_notebook_context(reader)
    assert "Today's log" in ctx
    assert "Built notebook context" in ctx


def test_shows_no_log_message_when_absent(reader: NotebookReader):
    ctx = build_notebook_context(reader)
    assert "No log entry yet" in ctx


def test_includes_recent_activity(reader: NotebookReader):
    ctx = build_notebook_context(reader)
    assert "Recent activity" in ctx


def test_includes_tool_usage_guidance(reader: NotebookReader):
    ctx = build_notebook_context(reader)
    assert "notebook_search" in ctx
    assert "notebook_read" in ctx
    assert "notebook_recent" in ctx
