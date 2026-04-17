from pathlib import Path

import pytest

from forge.notebook import NotebookWriteError
from forge.notebook.writer import ALLOWED_WRITE_PREFIXES, NotebookWriter


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    for d in ("Wiki", "Fields", "Log", "People", "+Templates"):
        (tmp_path / d).mkdir()
    return tmp_path


def test_write_wiki_accepted(vault: Path):
    writer = NotebookWriter(vault)
    writer.write("Wiki/OpenClaw.md", "# OpenClaw\n\nNotes.")
    assert (vault / "Wiki" / "OpenClaw.md").read_text() == "# OpenClaw\n\nNotes."


def test_write_fields_accepted(vault: Path):
    writer = NotebookWriter(vault)
    writer.write("Fields/Redpanda/Note.md", "content")
    assert (vault / "Fields" / "Redpanda" / "Note.md").read_text() == "content"


def test_write_log_accepted(vault: Path):
    writer = NotebookWriter(vault)
    writer.write("Log/2026-04-12.md", "daily")
    assert (vault / "Log" / "2026-04-12.md").read_text() == "daily"


def test_write_people_accepted(vault: Path):
    writer = NotebookWriter(vault)
    writer.write("People/Alice.md", "# Alice")
    assert (vault / "People" / "Alice.md").read_text() == "# Alice"


def test_write_templates_rejected(vault: Path):
    writer = NotebookWriter(vault)
    with pytest.raises(NotebookWriteError):
        writer.write("+Templates/Daily.md", "no")


def test_write_root_rejected(vault: Path):
    writer = NotebookWriter(vault)
    with pytest.raises(NotebookWriteError):
        writer.write("README.md", "no")


def test_write_rejects_path_traversal(vault: Path):
    writer = NotebookWriter(vault)
    with pytest.raises(NotebookWriteError):
        writer.write("Wiki/../../etc/passwd", "no")


def test_write_rejects_absolute_path(vault: Path):
    writer = NotebookWriter(vault)
    with pytest.raises(NotebookWriteError):
        writer.write("/etc/passwd", "no")


def test_write_rejects_base_file_in_allowed_dir(vault: Path):
    writer = NotebookWriter(vault)
    with pytest.raises(NotebookWriteError):
        writer.write("Wiki/Index.base", "no")


def test_allowed_prefixes_exposed():
    assert "Wiki/" in ALLOWED_WRITE_PREFIXES
    assert "Fields/" in ALLOWED_WRITE_PREFIXES
    assert "Log/" in ALLOWED_WRITE_PREFIXES
    assert "People/" in ALLOWED_WRITE_PREFIXES
    assert "Projects/" in ALLOWED_WRITE_PREFIXES


def test_append_creates_file_if_missing(vault: Path):
    writer = NotebookWriter(vault)
    writer.append("Log/2026-04-12.md", "first line\n")
    assert (vault / "Log" / "2026-04-12.md").read_text() == "first line\n"


def test_append_extends_existing_file(vault: Path):
    (vault / "Log" / "2026-04-12.md").write_text("existing\n")
    writer = NotebookWriter(vault)
    writer.append("Log/2026-04-12.md", "added\n")
    assert (vault / "Log" / "2026-04-12.md").read_text() == "existing\nadded\n"


def test_append_enforces_allowlist(vault: Path):
    writer = NotebookWriter(vault)
    with pytest.raises(NotebookWriteError):
        writer.append("+Templates/Daily.md", "no")
