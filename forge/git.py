import asyncio
import logging
import os

logger = logging.getLogger(__name__)


class GitOps:
    def __init__(self, workspace_dir: str):
        self._workspace_dir = workspace_dir
        os.makedirs(workspace_dir, exist_ok=True)

    async def ensure_repo(self, source: str, repo_name: str) -> str:
        # Prefer the host/owner/repo layout used by the repo registry.
        # For a GitHub source "owner/repo", check github.com/owner/repo first
        # so the agent reuses an existing checkout rather than cloning a copy.
        parts = repo_name.split("/")
        if len(parts) == 2:
            owner, name = parts
            preferred = os.path.join(self._workspace_dir, "github.com", owner, name)
            if os.path.exists(preferred):
                await self._run(["git", "fetch", "--all"], cwd=preferred)
                return preferred
            # Clone into the preferred location so future tasks reuse it.
            os.makedirs(os.path.dirname(preferred), exist_ok=True)
            await self._run(["git", "clone", source, preferred])
            return preferred

        # Fallback for bare repo names with no owner segment.
        repo_path = os.path.join(self._workspace_dir, parts[-1])
        if os.path.exists(repo_path):
            await self._run(["git", "fetch", "--all"], cwd=repo_path)
            return repo_path
        await self._run(["git", "clone", source, repo_path])
        return repo_path

    async def create_worktree(self, repo_path: str, branch_name: str) -> str:
        worktree_dir = os.path.join(repo_path, ".worktrees")
        os.makedirs(worktree_dir, exist_ok=True)
        worktree_path = os.path.join(worktree_dir, branch_name)
        default_branch = await self._get_default_branch(repo_path)
        await self._run(
            ["git", "worktree", "add", worktree_path, "-b", branch_name, default_branch],
            cwd=repo_path,
        )
        return worktree_path

    async def cleanup_worktree(self, repo_path: str, worktree_path: str):
        await self._run(["git", "worktree", "remove", worktree_path, "--force"], cwd=repo_path)

    async def get_diff(self, worktree_path: str, base_branch: str) -> str:
        return await self._run(["git", "diff", f"{base_branch}...HEAD"], cwd=worktree_path)

    async def get_working_tree_changes(self, path: str) -> list[str]:
        output = await self._run(["git", "status", "--porcelain"], cwd=path)
        files: list[str] = []
        for line in output.splitlines():
            if not line.strip():
                continue
            # porcelain format: XY <space> filename   (XY is 2 char status)
            # for renames: "R  old -> new"
            rest = line[3:] if len(line) > 3 else ""
            if " -> " in rest:
                rest = rest.split(" -> ", 1)[1]
            files.append(rest.strip())
        return files

    async def get_changed_files(self, worktree_path: str, base_branch: str = "main") -> list[str]:
        output = await self._run(
            ["git", "diff", "--name-only", f"{base_branch}...HEAD"],
            cwd=worktree_path,
        )
        return [line.strip() for line in output.splitlines() if line.strip()]

    async def commit_all(self, worktree_path: str, message: str) -> None:
        await self._run(["git", "add", "-A"], cwd=worktree_path)
        status = await self._run(["git", "status", "--porcelain"], cwd=worktree_path)
        if not status.strip():
            raise RuntimeError("commit_all called but nothing staged")
        await self._run(["git", "commit", "-m", message], cwd=worktree_path)

    async def create_pr(
        self,
        worktree_path: str,
        title: str,
        body: str,
        base_branch: str | None = None,
    ) -> str:
        branch = (
            await self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=worktree_path)
        ).strip()
        await self._run(["git", "push", "-u", "origin", branch], cwd=worktree_path)
        base = base_branch or await self._get_default_branch(worktree_path)
        result = await self._run(
            ["gh", "pr", "create", "--base", base, "--head", branch, "--title", title, "--body", body],
            cwd=worktree_path,
        )
        return result.strip()

    async def get_existing_pr_url(self, worktree_path: str) -> str | None:
        """Return the URL of an OPEN PR for the worktree's current branch, or
        None when there is none. Uses `gh pr list --head <branch> --state open`,
        which (unlike `gh pr view`) ignores closed/merged PRs — so a follow-up
        delivering to a branch whose prior PR was merged correctly opens a new
        one. `gh pr list` exits 0 with empty output when no open PR exists;
        RuntimeError covers git/gh/auth failures."""
        try:
            branch = (
                await self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=worktree_path)
            ).strip()
            out = await self._run(
                ["gh", "pr", "list", "--head", branch, "--state", "open",
                 "--json", "url", "-q", ".[0].url"],
                cwd=worktree_path,
            )
        except RuntimeError:
            return None
        url = out.strip()
        return url or None

    async def push_branch(self, worktree_path: str) -> None:
        """Push the worktree's current branch to origin (updates an open PR)."""
        branch = (
            await self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=worktree_path)
        ).strip()
        await self._run(["git", "push", "-u", "origin", branch], cwd=worktree_path)

    async def prune_worktrees(self, repo_path: str) -> None:
        """Drop stale worktree registrations after a removal."""
        await self._run(["git", "worktree", "prune"], cwd=repo_path)

    async def _get_default_branch(self, repo_path: str) -> str:
        # Try origin/HEAD first (works for cloned repos with a remote)
        try:
            result = await self._run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                cwd=repo_path,
            )
            return result.strip().split("/")[-1]
        except RuntimeError:
            pass

        # Fall back to detecting the current local branch (handles local-only repos)
        try:
            result = await self._run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
            )
            branch = result.strip()
            if branch and branch != "HEAD":
                return branch
        except RuntimeError:
            pass

        # Last resort default
        return "main"

    async def _run(self, cmd: list[str], cwd: str | None = None) -> str:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            error_msg = stderr.decode().strip()
            cmd_str = " ".join(cmd[:3]) + " ..."  # truncate to avoid leaking secrets
            logger.error("Git command failed: %s\n%s", cmd_str, error_msg)
            raise RuntimeError(f"Git command failed (rc={proc.returncode}): {error_msg}")
        return stdout.decode()
