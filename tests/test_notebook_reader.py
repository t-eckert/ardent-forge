from pathlib import Path

import pytest

from forge.notebook.reader import NotebookReader


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    (tmp_path / "Wiki").mkdir()
    (tmp_path / "Wiki" / "Kubernetes.md").write_text("# Kubernetes\n\nNotes.")
    (tmp_path / "Fields" / "Redpanda").mkdir(parents=True)
    (tmp_path / "Fields" / "Redpanda" / "Customers.md").write_text("# Customers")
    return tmp_path


def test_read_returns_file_contents(vault: Path):
    reader = NotebookReader(vault)
    assert reader.read("Wiki/Kubernetes.md") == "# Kubernetes\n\nNotes."


def test_read_rejects_path_traversal(vault: Path):
    reader = NotebookReader(vault)
    with pytest.raises(ValueError):
        reader.read("../etc/passwd")


def test_read_rejects_absolute_path(vault: Path):
    reader = NotebookReader(vault)
    with pytest.raises(ValueError):
        reader.read("/etc/passwd")


def test_read_missing_file_raises_filenotfound(vault: Path):
    reader = NotebookReader(vault)
    with pytest.raises(FileNotFoundError):
        reader.read("Wiki/Does-Not-Exist.md")
