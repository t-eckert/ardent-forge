from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


class UploadService:
    def __init__(self, upload_dir: Path) -> None:
        self._dir = upload_dir

    def ensure_dir(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, content: bytes, original_name: str) -> Path:
        self.ensure_dir()
        suffix = Path(original_name).suffix if original_name else ""
        if not suffix:
            suffix = ".png"
        stem = Path(original_name).stem if original_name else ""
        if not stem:
            stem = "screenshot"
        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")
        dest = self._dir / f"{stem}-{ts}{suffix}"
        dest.write_bytes(content)
        return dest

    def get_latest(self) -> Path | None:
        self.ensure_dir()
        files = [f for f in self._dir.iterdir() if f.is_file()]
        if not files:
            return None
        return max(files, key=lambda f: f.stat().st_mtime)

    def delete_old_files(self, max_age_days: int = 7) -> int:
        self.ensure_dir()
        cutoff = datetime.now().timestamp() - max_age_days * 86400
        deleted = 0
        for f in self._dir.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                log.debug("Deleted old upload: %s", f.name)
                deleted += 1
        return deleted
