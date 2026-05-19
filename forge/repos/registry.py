import asyncio
import logging
from pathlib import Path

import yaml

from forge.repos.models import Repo, RepoConfig

logger = logging.getLogger(__name__)


class RepoRegistry:
    def __init__(self, workspace_dir: str):
        self._workspace_dir = Path(workspace_dir)
        self._repos: dict[str, Repo] = {}

    async def scan(self) -> list[Repo]:
        repos: list[Repo] = []
        if not self._workspace_dir.exists():
            logger.warning("Workspace directory %s does not exist; no repos loaded", self._workspace_dir)
            return repos
        for entry in sorted(self._workspace_dir.iterdir()):
            if not entry.is_dir() or not (entry / ".git").exists():
                continue
            try:
                repo = await self._load_repo(entry)
                repos.append(repo)
                self._repos[repo.name] = repo
            except Exception:
                logger.warning("Failed to load repo at %s", entry, exc_info=True)
        logger.info("Repo registry: %d repos found in %s", len(repos), self._workspace_dir)
        return repos

    def list(self) -> list[Repo]:
        return list(self._repos.values())

    def get(self, name: str) -> Repo | None:
        return self._repos.get(name)

    def config(self, name: str) -> RepoConfig:
        repo = self._repos.get(name)
        if repo is None:
            return RepoConfig()
        return self._load_config(Path(repo.path)) or RepoConfig()

    async def _load_repo(self, path: Path) -> Repo:
        default_branch = await self._get_default_branch(path)
        config = self._load_config(path)
        return Repo(
            name=path.name,
            path=str(path),
            default_branch=default_branch,
            dev_port=config.dev_port if config else None,
        )

    def _load_config(self, path: Path) -> RepoConfig | None:
        config_file = path / "repo.yaml"
        if not config_file.exists():
            return None
        try:
            data = yaml.safe_load(config_file.read_text()) or {}
            return RepoConfig(**data)
        except Exception:
            logger.warning("Failed to parse repo.yaml at %s", path, exc_info=True)
            return None

    async def _get_default_branch(self, path: Path) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "symbolic-ref", "refs/remotes/origin/HEAD",
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
