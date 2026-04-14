"""/api/connectors — roster + health across all registered connectors."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/connectors")


@router.get("")
async def list_connectors(request: Request):
    registry = getattr(request.app.state, "connectors", None)
    if registry is None:
        return []
    return [
        {
            "name": c.name,
            "tools": [
                {"name": t.name, "description": t.description, "long_running": t.long_running}
                for t in c.tools
            ],
        }
        for c in registry.all()
    ]


@router.get("/health")
async def connectors_health(request: Request):
    registry = getattr(request.app.state, "connectors", None)
    if registry is None:
        return {}
    return await registry.health_check()
