"""/api/agents — registered agent roster for the UI's Library/Agents facet.

Read-only. Lists every agent's task_type, stages, and declared connectors
so the UI can render the agent doc surface without the frontend mocking it.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/agents")


def _registry(request: Request):
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None or orchestrator.agents is None:
        return None
    return orchestrator.agents


@router.get("")
async def list_agents(request: Request):
    registry = _registry(request)
    if registry is None:
        return []
    return [
        {
            "name": getattr(a, "name", a.task_type),
            "task_type": a.task_type,
            "stages": list(a.stages),
            "connectors": list(a.connectors),
        }
        for a in registry.list()
    ]


@router.get("/{task_type}")
async def get_agent(task_type: str, request: Request):
    registry = _registry(request)
    agent = registry.get(task_type) if registry else None
    if agent is None:
        raise HTTPException(status_code=404, detail=f"No agent for task_type: {task_type}")
    return {
        "name": getattr(agent, "name", agent.task_type),
        "task_type": agent.task_type,
        "stages": list(agent.stages),
        "connectors": list(agent.connectors),
    }
