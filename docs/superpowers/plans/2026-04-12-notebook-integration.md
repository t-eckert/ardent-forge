# Notebook Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Ardent Forge read/write access to the user's Obsidian Notebook via a syncshot-backed clone on the Bee Link, exposed as injectable `NotebookReader` / `NotebookWriter` services.

**Architecture:** The Notebook is cloned on the box at `/data/ardent-forge/notebook/`. A systemd-run `syncshot` loop auto-commits and pushes every 30s. Forge reads via `NotebookReader` (ripgrep + wikilink resolution) and writes via `NotebookWriter` (allowlist-enforced, atomic). Reader/writer are constructed in `forge/main.py` and injectable into handlers and the chat endpoint.

**Tech Stack:** Python 3.13, pytest, pytest-asyncio, ripgrep (system), git (system), systemd, NixOS. Vendors `syncshot.py` from `github.com/t-eckert/syncshot`.

**Spec:** `docs/superpowers/specs/2026-04-12-notebook-integration-design.md`

---

## File Structure

**Create:**
- `forge/notebook/__init__.py` — package init, re-exports the public API
- `forge/notebook/errors.py` — `NotebookWriteError`
- `forge/notebook/reader.py` — `NotebookReader`, `SearchHit`
- `forge/notebook/writer.py` — `NotebookWriter`, `ALLOWED_WRITE_PREFIXES`
- `tests/test_notebook_reader.py`
- `tests/test_notebook_writer.py`
- `tests/test_notebook_syncshot.py` — integration test against a bare local repo
- `scripts/syncshot.py` — vendored copy of `github.com/t-eckert/syncshot/syncshot.py`
- `nix/services/notebook-sync.nix` — systemd unit

**Modify:**
- `forge/config.py` — add `notebook_dir: str` setting
- `forge/main.py` — construct reader/writer, log when disabled
- `nix/configuration.nix` — import the new service

---

## Task 1: Vendor syncshot

**Files:**
- Create: `scripts/syncshot.py`

- [ ] **Step 1: Copy the vendored script**

Copy `/Users/thomaseckert/Repos/github.com/t-eckert/syncshot/syncshot.py` verbatim to `scripts/syncshot.py`. Prepend a one-line header comment:

```python
# Vendored from github.com/t-eckert/syncshot at v1 (2026-04-12).
# Do not edit in place — update upstream and re-vendor.
```

- [ ] **Step 2: Verify it runs**

Run: `python3 scripts/syncshot.py --help`
Expected: prints usage with `--period` and `--debug` flags.

- [ ] **Step 3: Commit**

```bash
git add scripts/syncshot.py
git commit -m "feat(notebook): vendor syncshot for auto-sync loop"
```

---

## Task 2: Error type

**Files:**
- Create: `forge/notebook/__init__.py`
- Create: `forge/notebook/errors.py`

- [ ] **Step 1: Create the package init**

`forge/notebook/__init__.py`:
```python
from forge.notebook.errors import NotebookWriteError

__all__ = ["NotebookWriteError"]
```

- [ ] **Step 2: Create the error type**

`forge/notebook/errors.py`:
```python
class NotebookWriteError(Exception):
    """Raised when a notebook write is rejected (bad path, outside allowlist)."""
```

- [ ] **Step 3: Commit**

```bash
git add forge/notebook/__init__.py forge/notebook/errors.py
git commit -m "feat(notebook): add package and error type"
```

---

## Task 3: `NotebookReader.read` and path-traversal guard

**Files:**
- Create: `forge/notebook/reader.py`
- Create: `tests/test_notebook_reader.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_notebook_reader.py`:
```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `uv run pytest tests/test_notebook_reader.py -v`
Expected: FAIL — `NotebookReader` does not exist.

- [ ] **Step 3: Implement `NotebookReader` with `read`**

`forge/notebook/reader.py`:
```python
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchHit:
    path: str
    line_number: int
    line: str


class NotebookReader:
    """Read-only access to the Obsidian Notebook vault."""

    def __init__(self, root: Path):
        self._root = root.resolve()
        if not self._root.is_dir():
            raise FileNotFoundError(f"Notebook root does not exist: {self._root}")
        if shutil.which("rg") is None:
            raise RuntimeError("ripgrep (rg) is required for NotebookReader")

    def _resolve(self, path: str) -> Path:
        if path.startswith("/"):
            raise ValueError(f"Absolute paths not allowed: {path}")
        candidate = (self._root / path).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as e:
            raise ValueError(f"Path escapes notebook root: {path}") from e
        return candidate

    def read(self, path: str) -> str:
        return self._resolve(path).read_text()
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `uv run pytest tests/test_notebook_reader.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add forge/notebook/reader.py tests/test_notebook_reader.py
git commit -m "feat(notebook): add NotebookReader.read with path guards"
```

---

## Task 4: `NotebookReader.list_dir` and `exists`

**Files:**
- Modify: `forge/notebook/reader.py`
- Modify: `tests/test_notebook_reader.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_notebook_reader.py`:
```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `uv run pytest tests/test_notebook_reader.py -v`
Expected: new tests FAIL with `AttributeError` on `list_dir` / `exists`.

- [ ] **Step 3: Implement the methods**

Append to `NotebookReader`:
```python
    def list_dir(self, path: str) -> list[str]:
        target = self._resolve(path) if path else self._root
        if not target.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")
        return [p.name for p in target.iterdir()]

    def exists(self, path: str) -> bool:
        try:
            return self._resolve(path).exists()
        except ValueError:
            return False
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `uv run pytest tests/test_notebook_reader.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add forge/notebook/reader.py tests/test_notebook_reader.py
git commit -m "feat(notebook): add NotebookReader.list_dir and exists"
```

---

## Task 5: `NotebookReader.search` (ripgrep)

**Files:**
- Modify: `forge/notebook/reader.py`
- Modify: `tests/test_notebook_reader.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_notebook_reader.py`:
```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `uv run pytest tests/test_notebook_reader.py -v -k search`
Expected: FAIL — `search` not implemented.

- [ ] **Step 3: Implement `search`**

Append to `NotebookReader`:
```python
    def search(self, query: str, path_prefix: str | None = None) -> list[SearchHit]:
        target = self._resolve(path_prefix) if path_prefix else self._root
        result = subprocess.run(
            ["rg", "--no-heading", "--line-number", "--color=never", query, str(target)],
            capture_output=True,
            text=True,
        )
        # rg exit code 1 means no matches — that's not an error
        if result.returncode not in (0, 1):
            raise RuntimeError(f"ripgrep failed: {result.stderr}")
        hits: list[SearchHit] = []
        for line in result.stdout.splitlines():
            # Format: /abs/path:lineno:content
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            abs_path, lineno, content = parts
            rel = str(Path(abs_path).relative_to(self._root))
            hits.append(SearchHit(path=rel, line_number=int(lineno), line=content))
        return hits
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `uv run pytest tests/test_notebook_reader.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add forge/notebook/reader.py tests/test_notebook_reader.py
git commit -m "feat(notebook): add NotebookReader.search via ripgrep"
```

---

## Task 6: `NotebookReader.resolve_wikilink`

**Files:**
- Modify: `forge/notebook/reader.py`
- Modify: `tests/test_notebook_reader.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_notebook_reader.py`:
```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `uv run pytest tests/test_notebook_reader.py -v -k wikilink`
Expected: FAIL — `resolve_wikilink` not implemented.

- [ ] **Step 3: Implement `resolve_wikilink`**

Append to `NotebookReader`:
```python
    def resolve_wikilink(self, name: str) -> Path | None:
        filename = f"{name}.md"
        matches = list(self._root.rglob(filename))
        if not matches:
            return None
        # Shortest path (fewest parts) wins — matches Obsidian behavior.
        best = min(matches, key=lambda p: len(p.relative_to(self._root).parts))
        return best.relative_to(self._root)
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `uv run pytest tests/test_notebook_reader.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add forge/notebook/reader.py tests/test_notebook_reader.py
git commit -m "feat(notebook): add NotebookReader.resolve_wikilink"
```

---

## Task 7: Export reader from package

**Files:**
- Modify: `forge/notebook/__init__.py`

- [ ] **Step 1: Update the package init**

`forge/notebook/__init__.py`:
```python
from forge.notebook.errors import NotebookWriteError
from forge.notebook.reader import NotebookReader, SearchHit

__all__ = ["NotebookReader", "NotebookWriteError", "SearchHit"]
```

- [ ] **Step 2: Verify import works**

Run: `uv run python -c "from forge.notebook import NotebookReader, SearchHit, NotebookWriteError; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add forge/notebook/__init__.py
git commit -m "feat(notebook): export reader from package"
```

---

## Task 8: `NotebookWriter.write` with allowlist

**Files:**
- Create: `forge/notebook/writer.py`
- Create: `tests/test_notebook_writer.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_notebook_writer.py`:
```python
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


def test_write_people_rejected(vault: Path):
    writer = NotebookWriter(vault)
    with pytest.raises(NotebookWriteError):
        writer.write("People/Alice.md", "no")


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
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `uv run pytest tests/test_notebook_writer.py -v`
Expected: FAIL — `NotebookWriter` does not exist.

- [ ] **Step 3: Implement `NotebookWriter`**

`forge/notebook/writer.py`:
```python
import logging
import os
import tempfile
from pathlib import Path

from forge.notebook.errors import NotebookWriteError

logger = logging.getLogger(__name__)

ALLOWED_WRITE_PREFIXES = ("Wiki/", "Fields/", "Log/")


class NotebookWriter:
    """Allowlist-enforced, atomic writes to the Obsidian Notebook vault."""

    def __init__(self, root: Path):
        self._root = root.resolve()
        if not self._root.is_dir():
            raise FileNotFoundError(f"Notebook root does not exist: {self._root}")

    def _validate_and_resolve(self, path: str) -> Path:
        if path.startswith("/"):
            raise NotebookWriteError(f"Absolute paths not allowed: {path}")
        if not any(path.startswith(prefix) for prefix in ALLOWED_WRITE_PREFIXES):
            raise NotebookWriteError(
                f"Path not in allowlist {ALLOWED_WRITE_PREFIXES}: {path}"
            )
        if path.endswith(".base"):
            raise NotebookWriteError(f"Cannot write .base files: {path}")
        candidate = (self._root / path).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as e:
            raise NotebookWriteError(f"Path escapes notebook root: {path}") from e
        return candidate

    def write(self, path: str, content: str) -> None:
        target = self._validate_and_resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: temp file in same dir + os.replace
        fd, tmp_path = tempfile.mkstemp(dir=target.parent, prefix=".tmp-", suffix=".md")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            os.replace(tmp_path, target)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `uv run pytest tests/test_notebook_writer.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add forge/notebook/writer.py tests/test_notebook_writer.py
git commit -m "feat(notebook): add NotebookWriter.write with allowlist"
```

---

## Task 9: `NotebookWriter.append`

**Files:**
- Modify: `forge/notebook/writer.py`
- Modify: `tests/test_notebook_writer.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_notebook_writer.py`:
```python
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
        writer.append("People/Alice.md", "no")
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `uv run pytest tests/test_notebook_writer.py -v -k append`
Expected: FAIL — `append` not implemented.

- [ ] **Step 3: Implement `append`**

Append to `NotebookWriter`:
```python
    def append(self, path: str, content: str) -> None:
        target = self._validate_and_resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a") as f:
            f.write(content)
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `uv run pytest tests/test_notebook_writer.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add forge/notebook/writer.py tests/test_notebook_writer.py
git commit -m "feat(notebook): add NotebookWriter.append"
```

---

## Task 10: Export writer from package

**Files:**
- Modify: `forge/notebook/__init__.py`

- [ ] **Step 1: Update the package init**

`forge/notebook/__init__.py`:
```python
from forge.notebook.errors import NotebookWriteError
from forge.notebook.reader import NotebookReader, SearchHit
from forge.notebook.writer import ALLOWED_WRITE_PREFIXES, NotebookWriter

__all__ = [
    "ALLOWED_WRITE_PREFIXES",
    "NotebookReader",
    "NotebookWriteError",
    "NotebookWriter",
    "SearchHit",
]
```

- [ ] **Step 2: Verify import works**

Run: `uv run python -c "from forge.notebook import NotebookWriter, NotebookReader; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add forge/notebook/__init__.py
git commit -m "feat(notebook): export writer from package"
```

---

## Task 11: `FORGE_NOTEBOOK_DIR` setting

**Files:**
- Modify: `forge/config.py`
- Create: `tests/test_notebook_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_notebook_config.py`:
```python
import os
from unittest.mock import patch

from forge.config import Settings


def test_notebook_dir_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("FORGE_NOTEBOOK_DIR", None)
        settings = Settings()
        assert settings.notebook_dir == "/data/ardent-forge/notebook"


def test_notebook_dir_env_override():
    with patch.dict(os.environ, {"FORGE_NOTEBOOK_DIR": "/tmp/my-vault"}):
        settings = Settings()
        assert settings.notebook_dir == "/tmp/my-vault"
```

- [ ] **Step 2: Run test and verify it fails**

Run: `uv run pytest tests/test_notebook_config.py -v`
Expected: FAIL — `notebook_dir` attribute missing.

- [ ] **Step 3: Add the setting**

Modify `forge/config.py`, add after the `workspace_dir` line:
```python
    # Notebook (Obsidian vault)
    notebook_dir: str = "/data/ardent-forge/notebook"
```

- [ ] **Step 4: Run test and verify it passes**

Run: `uv run pytest tests/test_notebook_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/config.py tests/test_notebook_config.py
git commit -m "feat(notebook): add FORGE_NOTEBOOK_DIR setting"
```

---

## Task 12: Wire reader/writer into `forge/main.py`

**Files:**
- Modify: `forge/main.py`

- [ ] **Step 1: Construct reader/writer with graceful fallback**

In `forge/main.py`, inside `run()` inside the `lifespan` function, after the `store = TaskStore(db)` line, add:

```python
        from pathlib import Path

        from forge.notebook import NotebookReader, NotebookWriter

        notebook_reader: NotebookReader | None = None
        notebook_writer: NotebookWriter | None = None
        notebook_path = Path(settings.notebook_dir)
        if notebook_path.is_dir():
            try:
                notebook_reader = NotebookReader(notebook_path)
                notebook_writer = NotebookWriter(notebook_path)
            except Exception as e:
                import logging

                logging.getLogger(__name__).warning(
                    f"Notebook disabled: {e}"
                )
        else:
            import logging

            logging.getLogger(__name__).warning(
                f"Notebook directory {notebook_path} not found; notebook features disabled"
            )
```

(These variables are unused by handlers right now — they'll be consumed by future handlers and the chat endpoint. Constructing them at startup surfaces misconfiguration immediately.)

- [ ] **Step 2: Verify server still starts**

Run: `uv run python -c "from forge.main import create_app; app = create_app(); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest -x`
Expected: all tests pass (no regressions).

- [ ] **Step 4: Commit**

```bash
git add forge/main.py
git commit -m "feat(notebook): construct reader/writer at app startup"
```

---

## Task 13: Syncshot integration test

**Files:**
- Create: `tests/test_notebook_syncshot.py`

- [ ] **Step 1: Write the integration test**

`tests/test_notebook_syncshot.py`:
```python
"""Integration test: syncshot commits and pushes to a bare local remote."""

import shutil
import subprocess
import time
from pathlib import Path

import pytest


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "HOME": str(cwd),
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="git required")
def test_syncshot_commits_and_pushes(tmp_path: Path):
    # Set up: bare remote + working clone
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)

    work = tmp_path / "work"
    subprocess.run(["git", "clone", str(remote), str(work)], check=True)
    _git(work, "checkout", "-b", "main")
    (work / "README.md").write_text("init")
    _git(work, "add", "README.md")
    _git(work, "commit", "-m", "initial")
    _git(work, "push", "-u", "origin", "main")

    # Make a dirty change
    (work / "Wiki").mkdir()
    (work / "Wiki" / "Note.md").write_text("hello")

    # Run syncshot for a single cycle by invoking it with a short period,
    # then killing it after one iteration.
    script = Path(__file__).parent.parent / "scripts" / "syncshot.py"
    proc = subprocess.Popen(
        ["python3", str(script), "--period", "1"],
        cwd=work,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Give it time to commit and push
        time.sleep(3)
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    # Verify: remote has the new commit with the Wiki/Note.md change
    verify_clone = tmp_path / "verify"
    subprocess.run(["git", "clone", str(remote), str(verify_clone)], check=True)
    assert (verify_clone / "Wiki" / "Note.md").read_text() == "hello"
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/test_notebook_syncshot.py -v`
Expected: PASS. (Takes ~3 seconds.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_notebook_syncshot.py
git commit -m "test(notebook): integration test for syncshot loop"
```

---

## Task 14: NixOS service file

**Files:**
- Create: `nix/services/notebook-sync.nix`

- [ ] **Step 1: Write the service file**

`nix/services/notebook-sync.nix`:
```nix
# nix/services/notebook-sync.nix
#
# Runs syncshot against the local Notebook clone, committing and pushing
# every 30 seconds. Initial clone is performed by ExecStartPre if the
# directory is empty.
{ config, pkgs, lib, locals, ... }:

let
  notebookDir = "/data/ardent-forge/notebook";
  notebookRepo = "https://github.com/t-eckert/Notebook.git";
  repoDir = "/data/ardent-forge/repo";

  preStart = pkgs.writeShellScript "notebook-sync-pre" ''
    set -euo pipefail
    export PATH=${lib.makeBinPath [ pkgs.git pkgs.coreutils ]}:$PATH

    if [ ! -d "${notebookDir}/.git" ]; then
      echo "Cloning Notebook into ${notebookDir}"
      git clone "${notebookRepo}" "${notebookDir}"
    fi

    cd "${notebookDir}"
    git config user.name "Ardent Forge"
    git config user.email "forge@${locals.tailnetDomain}"
    # Use FORGE_GITHUB_TOKEN for auth via the credential helper
    git config credential.helper '!f() { echo "username=x-access-token"; echo "password=$FORGE_GITHUB_TOKEN"; }; f'
  '';
in {
  systemd.services.ardent-forge-notebook-sync = {
    description = "Ardent Forge — syncshot loop for the Notebook vault";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];

    path = with pkgs; [ git coreutils python313 ];

    environment = {
      HOME = "/home/${locals.username}";
    };

    serviceConfig = {
      Type = "simple";
      User = locals.username;
      Group = "users";
      WorkingDirectory = notebookDir;

      EnvironmentFile = "/etc/ardent-forge/op-token";

      ExecStartPre = "+${preStart}";
      ExecStart = pkgs.writeShellScript "notebook-sync-start" ''
        exec ${pkgs._1password-cli}/bin/op run \
          --env-file ${repoDir}/nix/services/notebook-sync.env \
          -- ${pkgs.python313}/bin/python3 ${repoDir}/scripts/syncshot.py --period 30
      '';

      Restart = "on-failure";
      RestartSec = 30;
    };
  };

  systemd.tmpfiles.rules = [
    "d ${notebookDir} 0750 ${locals.username} users -"
  ];

  # Env template — secrets resolved by `op run`
  environment.etc."ardent-forge/notebook-sync.env.example".text = ''
    FORGE_GITHUB_TOKEN=op://Ardent Forge/github-pat/credential
  '';
}
```

Also create the referenced env file committed into the repo:

```bash
mkdir -p nix/services
cat > nix/services/notebook-sync.env <<'EOF'
FORGE_GITHUB_TOKEN=op://Ardent Forge/github-pat/credential
EOF
```

- [ ] **Step 2: Verify the nix file parses**

Run: `nix-instantiate --parse nix/services/notebook-sync.nix >/dev/null && echo ok`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add nix/services/notebook-sync.nix nix/services/notebook-sync.env
git commit -m "feat(nix): add notebook-sync systemd service"
```

---

## Task 15: Wire the service into configuration

**Files:**
- Modify: `nix/configuration.nix`

- [ ] **Step 1: Import the service**

In `nix/configuration.nix`, in the `imports = [ ... ]` list, add `./services/notebook-sync.nix` alongside the other service imports.

Before:
```nix
    ./services/the-weather.nix
    ./services/autodeploy.nix
```

After:
```nix
    ./services/the-weather.nix
    ./services/autodeploy.nix
    ./services/notebook-sync.nix
```

- [ ] **Step 2: Verify the full flake evaluates**

Run: `nix flake check ./nix --no-build 2>&1 | head -40`
Expected: no evaluation errors (warnings about un-pinned inputs are fine).

- [ ] **Step 3: Commit**

```bash
git add nix/configuration.nix
git commit -m "feat(nix): enable notebook-sync service"
```

---

## Task 16: Deploy and verify on the Bee Link

**Files:** (none — verification only)

- [ ] **Step 1: Wait for autodeploy or deploy manually**

Autodeploy will pick up the new commits within 5 minutes. To force it:

```bash
ssh thomaseckert@ardent-forge.feist-gondola.ts.net "sudo systemctl start ardent-forge-autodeploy"
```

Expected: NTFY notification on `ardent-forge-deploy` topic with success.

- [ ] **Step 2: Verify the notebook-sync service is running**

```bash
ssh thomaseckert@ardent-forge.feist-gondola.ts.net "systemctl status ardent-forge-notebook-sync --no-pager | head -20"
```

Expected: `Active: active (running)`.

- [ ] **Step 3: Verify the Notebook clone exists**

```bash
ssh thomaseckert@ardent-forge.feist-gondola.ts.net "ls /data/ardent-forge/notebook | head -10"
```

Expected: lists `Wiki`, `Fields`, `Log`, `People`, etc.

- [ ] **Step 4: Verify sync round-trip**

On the box:

```bash
ssh thomaseckert@ardent-forge.feist-gondola.ts.net "cd /data/ardent-forge/notebook && echo 'test from forge' > Wiki/.forge-ping.md"
```

Wait 45 seconds. Then on your laptop, in the Notebook worktree:

```bash
cd ~/.claude-worktrees/Notebook/hopeful-greider
git pull
cat Wiki/.forge-ping.md
```

Expected: prints `test from forge`.

Clean up:

```bash
ssh thomaseckert@ardent-forge.feist-gondola.ts.net "cd /data/ardent-forge/notebook && rm Wiki/.forge-ping.md"
```

- [ ] **Step 5: No commit** — this task is verification only.

---

## Self-review

**Spec coverage:**
- Architecture (box layout, syncshot service) → Tasks 1, 14, 15, 16
- `NotebookReader` methods → Tasks 3, 4, 5, 6
- `NotebookWriter` methods → Tasks 8, 9
- Allowlist enforcement → Task 8
- Atomic writes → Task 8
- Wikilink resolution w/ shortest-path preference → Task 6
- Path-traversal guards → Tasks 3, 8
- `FORGE_NOTEBOOK_DIR` config → Task 11
- Graceful fallback when dir missing → Task 12
- Ripgrep validation at construction → Task 3
- Unit tests with temp-dir fake vault → Tasks 3-9
- Syncshot integration test → Task 13

All spec requirements are covered.

**Placeholder scan:** no TBD/TODO/"handle edge cases" — all steps contain concrete code or commands.

**Type consistency:** `NotebookReader`, `NotebookWriter`, `NotebookWriteError`, `SearchHit`, `ALLOWED_WRITE_PREFIXES` are defined before first use. Method names (`read`, `write`, `append`, `list_dir`, `exists`, `search`, `resolve_wikilink`) are consistent between tasks and tests.

---
