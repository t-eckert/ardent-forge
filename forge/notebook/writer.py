import logging
import os
import re
import tempfile
from pathlib import Path

from forge.notebook.errors import NotebookWriteError

logger = logging.getLogger(__name__)

ALLOWED_WRITE_PREFIXES = ("Wiki/", "Fields/", "Log/", "People/", "Projects/")
VALID_CHECKBOX_MARKERS = frozenset([" ", "x", "-", ">", "!", "~"])
_CHECKBOX_RE = re.compile(r"^(\s*- \[)([x\->!~ ])(\] )", re.MULTILINE)


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

    def update_checkbox(self, path: str, line_index: int, marker: str) -> None:
        """Replace the checkbox marker on a specific line (0-indexed)."""
        if marker not in VALID_CHECKBOX_MARKERS:
            raise ValueError(f"Invalid marker: {marker!r}")
        target = self._validate_and_resolve(path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {path}")
        lines = target.read_text().split("\n")
        if not (0 <= line_index < len(lines)):
            raise ValueError(f"Line {line_index} out of range (file has {len(lines)} lines)")
        line = lines[line_index]
        m = re.match(r"^(\s*- \[)[x\->!~ ](\] )", line)
        if not m:
            raise ValueError(f"Line {line_index} is not a checkbox item: {line!r}")
        lines[line_index] = m.group(1) + marker + m.group(2) + line[m.end():]
        self.write(path, "\n".join(lines))

    def append(self, path: str, content: str) -> None:
        target = self._validate_and_resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a") as f:
            f.write(content)
