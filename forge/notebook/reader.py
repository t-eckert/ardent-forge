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
