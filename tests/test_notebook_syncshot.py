"""Integration test: syncshot commits and pushes to a bare local remote."""

import os
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
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
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
