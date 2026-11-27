#!/usr/bin/env python3
"""Stop Remote Control sessions that have sat idle and remove their worktrees.

  claude-rc-reap [--idle-hours N] [--server PID] [--dry-run]

`claude remote-control --spawn=worktree` gives every session started from the
phone its own process and git worktree, and neither goes away when the session
is abandoned. For each running server this stops a spawned session, and
removes its worktree and `worktree-bridge-` branch, when all of these hold:

  - its transcript has not been written for N hours (default 48);
  - its worktree has no uncommitted changes;
  - its worktree has no commit that is on no remote.

A worktree left behind by a session that is already gone is held to the same
three. The session a server pre-creates in the checkout itself is never
touched. Anything that fails a check is reported and left alone. --server
limits the run to one server process.
"""

import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECTS = Path.home() / ".claude/projects"


def argv_of(pid):
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").split("\0")[:-1]
    except OSError:
        return []


def cwd_of(pid):
    try:
        return os.readlink(f"/proc/{pid}/cwd").removesuffix(" (deleted)")
    except OSError:
        return ""


def children(pid):
    listing = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout
    return [int(p) for p in listing.split()]


def git(directory, *args):
    return subprocess.run(["git", "-C", directory, *args], capture_output=True, text=True)


def idle_hours(worktree, pid):
    """Hours since the session's transcript was last written."""
    transcripts = PROJECTS / re.sub(r"[^A-Za-z0-9]", "-", worktree)
    times = [p.stat().st_mtime for p in transcripts.glob("*.jsonl")] if transcripts.is_dir() else []
    if not times and pid:
        times = [os.stat(f"/proc/{pid}").st_mtime]
    if not times and os.path.isdir(worktree):
        times = [os.stat(worktree).st_mtime]
    return (time.time() - max(times)) / 3600 if times else float("inf")


def spawned_worktrees(checkout):
    """{path: (branch, locked)} for the worktrees a server made under the checkout."""
    found = {}
    for block in git(checkout, "worktree", "list", "--porcelain").stdout.strip().split("\n\n"):
        fields = {key: value for key, _, value in (line.partition(" ") for line in block.splitlines())}
        path = fields.get("worktree", "")
        if "/.claude/worktrees/bridge-" in path:
            found[path] = (fields.get("branch", "").removeprefix("refs/heads/"), "locked" in fields)
    return found


def blocker(worktree):
    """Why the worktree must be kept, or None."""
    if not os.path.isdir(worktree):
        return None
    dirty = git(worktree, "status", "--porcelain").stdout.strip()
    if dirty:
        return f"{len(dirty.splitlines())} uncommitted changes"
    unpushed = git(worktree, "rev-list", "--count", "HEAD", "--not", "--remotes").stdout.strip()
    if unpushed not in ("", "0"):
        return f"{unpushed} commits on no remote"
    return None


def reap(server, limit, dry):
    checkout = cwd_of(server)
    sessions = {cwd_of(c): c for c in children(server) if "--session-id" in argv_of(c)}
    sessions.pop(checkout, None)
    worktrees = spawned_worktrees(checkout)

    for path in sorted(set(sessions) | set(worktrees)):
        if "/.claude/worktrees/" not in path:
            continue
        pid = sessions.get(path)
        name = Path(path).name
        idle = idle_hours(path, pid)
        if idle < limit:
            continue
        reason = blocker(path)
        if reason:
            print(f"keep {name}: idle {idle:.0f}h but {reason}")
            continue
        if dry:
            print(f"would reap {name}: idle {idle:.0f}h" + (f", pid {pid}" if pid else ", no session"))
            continue
        if pid:
            os.kill(pid, signal.SIGTERM)
            deadline = time.time() + 15
            while os.path.exists(f"/proc/{pid}") and time.time() < deadline:
                time.sleep(0.2)
        if path in worktrees:
            branch, locked = worktrees[path]
            # The lock is held for a session that is gone or was just stopped.
            if locked:
                git(checkout, "worktree", "unlock", path)
            removed = git(checkout, "worktree", "remove", path)
            if removed.returncode != 0:
                print(f"stopped {name} but its worktree stayed: {removed.stderr.strip()}")
                continue
            if branch.startswith("worktree-bridge-"):
                git(checkout, "branch", "-d", branch)
        print(f"reaped {name}: idle {idle:.0f}h" + (f", stopped pid {pid}" if pid else ", no session"))


def main():
    args = sys.argv[1:]
    limit = float(os.environ.get("CLAUDE_RC_IDLE_HOURS", "48"))
    if "--idle-hours" in args:
        limit = float(args[args.index("--idle-hours") + 1])
    servers = [
        int(p.name) for p in Path("/proc").iterdir()
        if p.name.isdigit()
        and (argv := argv_of(p.name))
        and Path(argv[0]).name == "claude"
        and "remote-control" in argv[1:3]
    ]
    if "--server" in args:
        only = int(args[args.index("--server") + 1])
        servers = [s for s in servers if s == only]
    for server in servers:
        reap(server, limit, "--dry-run" in args)


if __name__ == "__main__":
    main()
