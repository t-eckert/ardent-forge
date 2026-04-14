"""MemoryStore — filesystem-backed memory CRUD + MEMORY.md index regeneration."""

from pathlib import Path

import pytest

from forge.memory import INDEX_FILENAME, MemoryStore


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path)


def test_store_creates_root_dir(tmp_path):
    root = tmp_path / "mem"
    assert not root.exists()
    s = MemoryStore(root)
    assert root.is_dir()
    assert s.root == root


def test_write_and_get_round_trip(store: MemoryStore):
    e = store.write(
        name="User role",
        description="What Thomas does for a living + current projects",
        type="user",
        body="Software engineer at Redpanda. Personal projects include Ardent Forge.",
    )
    assert e.filename == "user_role.md"
    assert e.updated_at is not None

    got = store.get("user_role.md")
    assert got is not None
    assert got.name == "User role"
    assert got.type == "user"
    assert "Redpanda" in got.body


def test_write_accepts_explicit_filename(store: MemoryStore):
    e = store.write(
        name="Anything",
        description="x",
        type="user",
        body="b",
        filename="explicit.md",
    )
    assert e.filename == "explicit.md"
    assert store.get("explicit").slug == "explicit"


def test_write_rejects_unknown_type(store: MemoryStore):
    with pytest.raises(ValueError):
        store.write(name="x", description="y", type="bogus", body="z")  # type: ignore[arg-type]


def test_list_returns_entries_sorted(store: MemoryStore):
    store.write(name="Zebra", description="z", type="user", body="z")
    store.write(name="Alpha", description="a", type="user", body="a")
    names = [e.filename for e in store.list()]
    # Sorted by filename: alpha.md, zebra.md
    assert names == ["alpha.md", "zebra.md"]


def test_list_skips_index_file(store: MemoryStore):
    store.write(name="One", description="x", type="user", body="y")
    # MEMORY.md now exists but shouldn't appear in list()
    assert (store.root / INDEX_FILENAME).is_file()
    assert [e.filename for e in store.list()] == ["one.md"]


def test_remove(store: MemoryStore):
    store.write(name="X", description="x", type="user", body="y")
    assert store.remove("x.md") is True
    assert store.get("x.md") is None
    assert store.remove("x.md") is False  # second time


def test_index_groups_by_type(store: MemoryStore):
    store.write(name="Role", description="what user does", type="user", body="...")
    store.write(name="Mono numbers", description="style rule", type="feedback", body="...")
    store.write(name="Redpanda repo", description="repo notes", type="project", body="...")

    idx = store.read_index()
    # Groups are in the canonical order user → feedback → project → reference.
    assert idx.index("## user") < idx.index("## feedback") < idx.index("## project")
    assert "[Role](role.md) — what user does" in idx
    assert "[Mono numbers](mono_numbers.md) — style rule" in idx
    assert "[Redpanda repo](redpanda_repo.md) — repo notes" in idx


def test_index_updates_on_remove(store: MemoryStore):
    store.write(name="To keep", description="k", type="user", body="...")
    store.write(name="To remove", description="r", type="user", body="...")
    store.remove("to_remove.md")
    idx = store.read_index()
    assert "to_remove" not in idx
    assert "to_keep" in idx


def test_index_empty_when_no_entries(store: MemoryStore):
    # Fresh store, read_index() handles missing file.
    assert store.read_index() == ""


def test_parse_preserves_body(store: MemoryStore):
    body = "Multi-line body.\n\nWith paragraphs.\n\n- list\n- items\n"
    store.write(name="Multi", description="d", type="reference", body=body)
    got = store.get("multi.md")
    assert got.body.strip() == body.strip()


def test_rejects_traversal(store: MemoryStore):
    # Don't let a caller sneak out of the store via ../
    with pytest.raises(ValueError):
        store.get("../../../etc/passwd")
