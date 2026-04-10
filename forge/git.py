import asyncio
import logging
import os

logger = logging.getLogger(__name__)


class GitOps:
    def __init__(self, workspace_dir: str):
        self._workspace_dir = workspace_dir
        os.makedirs(workspace_dir, exist_ok=True)

    async def ensure_repo(self, source: str, repo_name: str) -> str:
        safe_name = repo_name.replace("/", "--")
        repo_path = os.path.join(self._workspace_dir, safe_name)
        if os.path.exists(repo_path):
            await self._run("git fetch --all", cwd=repo_path)
            return repo_path
        await self._run(f"git clone {source} {repo_path}")
        return repo_path

    async def create_worktree(self, repo_path: str, branch_name: str) -> str:
        worktree_dir = os.path.join(repo_path, ".worktrees")
        os.makedirs(worktree_dir, exist_ok=True)
        worktree_path = os.path.join(worktree_dir, branch_name)
        default_branch = await self._get_default_branch(repo_path)
        await self._run(
            f"git worktree add {worktree_path} -b {branch_name} {default_branch}",
            cwd=repo_path,
        )
        return worktree_path

    async def cleanup_worktree(self, repo_path: str, worktree_path: str):
        await self._run(f"git worktree remove {worktree_path} --force", cwd=repo_path)

    async def get_diff(self, worktree_path: str, base_branch: str) -> str:
        return await self._run(f"git diff {base_branch}...HEAD", cwd=worktree_path)

    async def create_pr(
        self,
        worktree_path: str,
        title: str,
        body: str,
        base_branch: str | None = None,
    ) -> str:
        branch = (
            await self._run("git rev-parse --abbrev-ref HEAD", cwd=worktree_path)
        ).strip()
        await self._run(f"git push -u origin {branch}", cwd=worktree_path)
        base = base_branch or await self._get_default_branch(worktree_path)
        result = await self._run(
            f'gh pr create --base {base} --head {branch} --title "{title}" --body "{body}"',
            cwd=worktree_path,
        )
        return result.strip()

    async def _get_default_branch(self, repo_path: str) -> str:
        # Try origin/HEAD first (works for cloned repos with a remote)
        try:
            result = await self._run(
                "git symbolic-ref refs/remotes/origin/HEAD",
                cwd=repo_path,
            )
            return result.strip().split("/")[-1]
        except RuntimeError:
            pass

        # Fall back to detecting the current local branch (handles local-only repos)
        try:
            result = await self._run(
                "git rev-parse --abbrev-ref HEAD",
                cwd=repo_path,
            )
            branch = result.strip()
            if branch and branch != "HEAD":
                return branch
        except RuntimeError:
            pass

        # Last resort default
        return "main"

    async def _run(self, cmd: str, cwd: str | None = None) -> str:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            error_msg = stderr.decode().strip()
            logger.error(f"Git command failed: {cmd}\n{error_msg}")
            raise RuntimeError(f"Git command failed: {cmd}\n{error_msg}")
        return stdout.decode()
