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

    def resolve_wikilink(self, name: str) -> Path | None:
        filename = f"{name}.md"
        matches = list(self._root.rglob(filename))
        if not matches:
            return None
        # Shortest path (fewest parts) wins — matches Obsidian behavior.
        best = min(matches, key=lambda p: len(p.relative_to(self._root).parts))
        return best.relative_to(self._root)
