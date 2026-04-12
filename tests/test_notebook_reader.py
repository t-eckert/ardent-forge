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


def test_list_dir_returns_entries(vault: Path):
    reader = NotebookReader(vault)
    entries = sorted(reader.list_dir("Wiki"))
    assert entries == ["Kubernetes.md"]


def test_list_dir_nested(vault: Path):
    reader = NotebookReader(vault)
    entries = sorted(reader.list_dir("Fields/Redpanda"))
    assert entries == ["Customers.md"]


def test_list_dir_empty_string_is_root(vault: Path):
    reader = NotebookReader(vault)
    entries = sorted(reader.list_dir(""))
    assert "Wiki" in entries
    assert "Fields" in entries


def test_exists_true(vault: Path):
    reader = NotebookReader(vault)
    assert reader.exists("Wiki/Kubernetes.md") is True


def test_exists_false(vault: Path):
    reader = NotebookReader(vault)
    assert reader.exists("Wiki/Does-Not-Exist.md") is False


def test_list_dir_rejects_traversal(vault: Path):
    reader = NotebookReader(vault)
    with pytest.raises(ValueError):
        reader.list_dir("../")


def test_search_finds_matches(vault: Path):
    (vault / "Wiki" / "Docker.md").write_text("container runtime notes")
    (vault / "Wiki" / "Kubernetes.md").write_text("Also a container tool")
    reader = NotebookReader(vault)
    hits = reader.search("container")
    paths = {h.path for h in hits}
    assert paths == {"Wiki/Docker.md", "Wiki/Kubernetes.md"}


def test_search_with_path_prefix(vault: Path):
    (vault / "Wiki" / "Docker.md").write_text("container runtime")
    (vault / "Fields" / "Redpanda" / "Notes.md").write_text("container orchestration")
    reader = NotebookReader(vault)
    hits = reader.search("container", path_prefix="Wiki")
    paths = {h.path for h in hits}
    assert paths == {"Wiki/Docker.md"}


def test_search_no_matches_returns_empty(vault: Path):
    reader = NotebookReader(vault)
    assert reader.search("zzz-never-matches-anything") == []


def test_resolve_wikilink_found(vault: Path):
    reader = NotebookReader(vault)
    result = reader.resolve_wikilink("Kubernetes")
    assert result == Path("Wiki/Kubernetes.md")


def test_resolve_wikilink_missing(vault: Path):
    reader = NotebookReader(vault)
    assert reader.resolve_wikilink("Does-Not-Exist") is None


def test_resolve_wikilink_prefers_shortest_path(vault: Path):
    (vault / "Notes.md").write_text("root level")
    (vault / "Fields" / "Redpanda" / "Notes.md").write_text("nested")
    reader = NotebookReader(vault)
    result = reader.resolve_wikilink("Notes")
    assert result == Path("Notes.md")
