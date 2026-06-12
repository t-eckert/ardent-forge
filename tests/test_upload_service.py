import os
import time
from pathlib import Path

import pytest

from forge.uploads import UploadService


@pytest.fixture
def upload_dir(tmp_path):
    return tmp_path / "uploads"


@pytest.fixture
def service(upload_dir):
    return UploadService(upload_dir)


def test_ensure_dir_creates_directory(service, upload_dir):
    assert not upload_dir.exists()
    service.ensure_dir()
    assert upload_dir.is_dir()


def test_save_file_returns_path_with_timestamp(service):
    path = service.save_file(b"data", "screenshot.png")
    assert path.exists()
    assert path.suffix == ".png"
    assert "screenshot-" in path.name


def test_save_file_preserves_extension(service):
    path = service.save_file(b"data", "capture.jpg")
    assert path.suffix == ".jpg"


def test_save_file_uses_screenshot_stem_for_unnamed_file(service):
    path = service.save_file(b"data", "")
    assert path.stem.startswith("screenshot-")


def test_save_file_writes_content(service):
    content = b"\x89PNG content"
    path = service.save_file(content, "image.png")
    assert path.read_bytes() == content


def test_get_latest_returns_none_when_empty(service):
    service.ensure_dir()
    assert service.get_latest() is None


def test_get_latest_returns_most_recent(service):
    service.save_file(b"first", "a.png")
    time.sleep(0.05)
    p2 = service.save_file(b"second", "b.png")
    assert service.get_latest() == p2


def test_delete_old_files_removes_stale(service, upload_dir):
    service.ensure_dir()
    old_file = upload_dir / "old.png"
    old_file.write_bytes(b"old")
    old_time = time.time() - 8 * 86400  # 8 days ago
    os.utime(old_file, (old_time, old_time))

    deleted = service.delete_old_files(max_age_days=7)

    assert deleted == 1
    assert not old_file.exists()


def test_delete_old_files_keeps_recent(service, upload_dir):
    service.ensure_dir()
    new_file = upload_dir / "new.png"
    new_file.write_bytes(b"new")

    deleted = service.delete_old_files(max_age_days=7)

    assert deleted == 0
    assert new_file.exists()


def test_delete_old_files_returns_zero_when_empty(service):
    service.ensure_dir()
    assert service.delete_old_files() == 0
