from pathlib import Path

import pytest

from forge.frontmatter import (
    SpecStatus,
    read_spec,
    update_spec_status,
    find_specs_by_status,
)


def test_read_spec_returns_status_and_body(tmp_path: Path):
    spec = tmp_path / "foo.md"
    spec.write_text("---\nstatus: ready-to-plan\ntitle: Foo\n---\n\n# Foo\nBody text\n")
    parsed = read_spec(spec)
    assert parsed.status == SpecStatus.READY_TO_PLAN
    assert parsed.title == "Foo"
    assert "Body text" in parsed.body
    assert parsed.path == spec


def test_read_spec_missing_status_returns_none(tmp_path: Path):
    spec = tmp_path / "foo.md"
    spec.write_text("---\ntitle: Foo\n---\n\nBody\n")
    parsed = read_spec(spec)
    assert parsed.status is None


def test_update_spec_status_preserves_other_fields(tmp_path: Path):
    spec = tmp_path / "foo.md"
    spec.write_text("---\nstatus: ready-to-plan\ntitle: Foo\n---\n\nBody\n")
    update_spec_status(spec, SpecStatus.PLANNED)
    again = read_spec(spec)
    assert again.status == SpecStatus.PLANNED
    assert again.title == "Foo"
    assert "Body" in again.body


def test_find_specs_by_status(tmp_path: Path):
    (tmp_path / "a.md").write_text("---\nstatus: ready-to-plan\n---\nA\n")
    (tmp_path / "b.md").write_text("---\nstatus: draft\n---\nB\n")
    (tmp_path / "c.md").write_text("---\nstatus: ready-to-plan\n---\nC\n")
    (tmp_path / "not-a-spec.txt").write_text("ignored")

    found = find_specs_by_status(tmp_path, SpecStatus.READY_TO_PLAN)
    names = sorted(p.name for p in found)
    assert names == ["a.md", "c.md"]
