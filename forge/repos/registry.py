from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from forge.repos.models import Project, Repo

logger = logging.getLogger(__name__)

# Matches https://host/owner/repo[.git] and git@host:owner/repo[.git]
_HTTPS_RE = re.compile(r"https?://([^/]+)/([^/]+)/([^/]+?)(?:\.git)?$")
_SSH_RE = re.compile(r"git@([^:]+):([^/]+)/([^/]+?)(?:\.git)?$")


def parse_clone_url(url: str) -> tuple[str, str, str, str]:
    """Return (host, owner, repo, https_clone_url) from any common git URL format.

    Also accepts bare 'owner/repo' shorthand (defaults host to github.com).
    Raises ValueError for unrecognised formats.
    """
    url = url.strip()

    for pattern in (_HTTPS_RE, _SSH_RE):
        m = pattern.match(url)
        if m:
            host, owner, repo = m.group(1), m.group(2), m.group(3)
            clone_url = f"https://{host}/{owner}/{repo}.git"
            return host, owner, repo, clone_url

    # Bare owner/repo shorthand
    if re.fullmatch(r"[^/\s]+/[^/\s]+", url):
        owner, repo = url.split("/", 1)
        host = "github.com"
        clone_url = f"https://{host}/{owner}/{repo}.git"
        return host, owner, repo, clone_url

    raise ValueError(f"Cannot parse clone URL: {url!r}")


class RepoRegistry:
    # github.com/owner/repo is 3 levels deep; allow a little headroom
    _MAX_SCAN_DEPTH = 4

    def __init__(self, workspace_dir: str, projects_dir: str | None = None):
        self._workspace_dir = Path(workspace_dir)
        self._projects_dir = Path(projects_dir) if projects_dir else None
        self._repos: dict[str, Repo] = {}
        self._projects: dict[str, Project] = {}

    async def scan(self) -> list[Repo]:
        repos: list[Repo] = []
        if not self._workspace_dir.exists():
            logger.warning(
                "Workspace directory %s does not exist; no repos loaded", self._workspace_dir
            )
            return repos
        for entry in sorted(self._find_repos(self._workspace_dir)):
            try:
                repo = await self._load_repo(entry)
                repos.append(repo)
                self._repos[repo.name] = repo
            except Exception:
                logger.warning("Failed to load repo at %s", entry, exc_info=True)
        logger.info("Repo registry: %d repos found in %s", len(repos), self._workspace_dir)
        return repos

    async def clone(self, url: str) -> Repo:
        """Clone a repo into workspace_dir/host/owner/repo and register it.

        If the destination already exists with a .git directory, the repo is
        registered without re-cloning. Raises ValueError for bad URLs and
        RuntimeError if git clone fails.
        """
        host, owner, repo_name, clone_url = parse_clone_url(url)
        dest = self._workspace_dir / host / owner / repo_name

        if not (dest / ".git").exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            await self._git_clone(clone_url, dest)
            logger.info("Cloned %s → %s", clone_url, dest)

        repo = await self._load_repo(dest)
        self._repos[repo.name] = repo
        return repo

    def _find_repos(self, root: Path) -> list[Path]:
        found: list[Path] = []
        self._walk(root, 0, found)
        return found

    def _walk(self, directory: Path, depth: int, found: list[Path]) -> None:
        if depth > self._MAX_SCAN_DEPTH:
            return
        if (directory / ".git").exists():
            found.append(directory)
            return  # don't recurse into nested repos
        if not directory.is_dir():
            return
        try:
            for entry in directory.iterdir():
                if entry.is_dir() and not entry.name.startswith("."):
                    self._walk(entry, depth + 1, found)
        except PermissionError:
            pass

    def list(self) -> list[Repo]:
        return list(self._repos.values())

    def get(self, name: str) -> Repo | None:
        return self._repos.get(name)

    async def scan_projects(self) -> list[Project]:
        projects: list[Project] = []
        if self._projects_dir is None or not self._projects_dir.exists():
            if self._projects_dir is not None:
                logger.warning("Projects directory %s does not exist", self._projects_dir)
            return projects
        for entry in sorted(self._projects_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            try:
                project = await self._load_project(entry)
                projects.append(project)
                self._projects[project.name] = project
            except Exception:
                logger.warning("Failed to load project at %s", entry, exc_info=True)
        logger.info("Project registry: %d projects found in %s", len(projects), self._projects_dir)
        return projects

    def list_projects(self) -> list[Project]:
        return list(self._projects.values())

    def get_project(self, name: str) -> Project | None:
        return self._projects.get(name)

    async def _load_project(self, path: Path) -> Project:
        repo_paths: list[Path] = []
        self._walk(path, 0, repo_paths)
        repos: list[Repo] = []
        for repo_path in sorted(repo_paths):
            try:
                default_branch = await self._get_default_branch(repo_path)
                try:
                    name = str(repo_path.relative_to(path))
                except ValueError:
                    name = repo_path.name
                repos.append(Repo(name=name, path=str(repo_path), default_branch=default_branch))
            except Exception:
                logger.warning("Failed to load repo at %s", repo_path, exc_info=True)
        return Project(name=path.name, path=str(path), repos=repos)

    async def _load_repo(self, path: Path) -> Repo:
        default_branch = await self._get_default_branch(path)
        try:
            name = str(path.relative_to(self._workspace_dir))
        except ValueError:
            name = path.name
        return Repo(
            name=name,
            path=str(path),
            default_branch=default_branch,
        )

    async def _git_clone(self, clone_url: str, dest: Path) -> None:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            clone_url,
            str(dest),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"git clone failed: {stderr.decode().strip()}")

    async def _get_default_branch(self, path: Path) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "symbolic-ref",
                "refs/remotes/origin/HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(path),
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                return stdout.decode().strip().split("/")[-1]
        except Exception:
            pass
        return "main"
