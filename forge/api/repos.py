from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from forge.repos.models import Repo
from forge.repos.registry import RepoRegistry, parse_clone_url

router = APIRouter()
_registry: RepoRegistry | None = None


def set_registry(registry: RepoRegistry) -> None:
    global _registry
    _registry = registry


class CloneRequest(BaseModel):
    url: str


@router.get("/api/repos")
async def list_repos() -> list[Repo]:
    if _registry is None:
        return []
    return _registry.list()


@router.post("/api/repos/clone")
async def clone_repo(req: CloneRequest) -> Repo:
    if _registry is None:
        raise HTTPException(status_code=503, detail="Repo registry not available")
    try:
        parse_clone_url(req.url)  # validate before doing any work
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    try:
        return await _registry.clone(req.url)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/repos/{name:path}")
async def get_repo(name: str) -> Repo | None:
    if _registry is None:
        return None
    return _registry.get(name)
