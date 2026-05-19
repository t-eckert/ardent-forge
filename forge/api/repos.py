from fastapi import APIRouter

from forge.repos.models import Repo
from forge.repos.registry import RepoRegistry

router = APIRouter()
_registry: RepoRegistry | None = None


def set_registry(registry: RepoRegistry) -> None:
    global _registry
    _registry = registry


@router.get("/api/repos")
async def list_repos() -> list[Repo]:
    if _registry is None:
        return []
    return _registry.list()


@router.get("/api/repos/{name}")
async def get_repo(name: str) -> Repo | None:
    if _registry is None:
        return None
    return _registry.get(name)
