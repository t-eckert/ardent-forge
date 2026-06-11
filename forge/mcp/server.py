"""Forge MCP server — exposes Forge's services to local Claude Code sessions.

A FastMCP streamable-HTTP server mounted into the Forge FastAPI app at /mcp.
Tools are thin wrappers over already-assembled services, injected via
``configure(...)`` (same pattern as forge/api/chat.py) so this module stays
import-light and avoids an import cycle with the coordinator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from forge.memory import VALID_TYPES, MemoryStore
from forge.models import Task, TaskSource, TaskStatus, TaskType

# Injected services — set by configure() during app lifespan. Typed loosely
# (coordinator/connectors/repo_registry/notebook_reader) to avoid import cycles.
_store = None
_memory: MemoryStore | None = None
_repo_registry = None
_coordinator = None  # has .nudge()
_connectors = None
_notebook_reader = None


def configure(
    *,
    store=None,
    memory=None,
    repo_registry=None,
    coordinator=None,
    connectors=None,
    notebook_reader=None,
) -> None:
    """Inject live services. Idempotent merge — only overwrites what's passed."""
    global _store, _memory, _repo_registry, _coordinator, _connectors, _notebook_reader
    if store is not None:
        _store = store
    if memory is not None:
        _memory = memory
    if repo_registry is not None:
        _repo_registry = repo_registry
    if coordinator is not None:
        _coordinator = coordinator
    if connectors is not None:
        _connectors = connectors
    if notebook_reader is not None:
        _notebook_reader = notebook_reader


async def dispatch_task(
    type: str, title: str, description: str, repo: str | None = None
) -> dict:
    """Queue a task for Forge's agent pipeline and start it processing now.

    Hands work off to a Forge agent (e.g. the Code agent runs Claude Code in a
    Zellij session). Returns immediately with the task id and status — this does
    NOT wait for completion. Poll get_task(id) or list_tasks() to observe progress
    and pick up the result (Code tasks expose zellij_session/attach_cmd in
    handler_data so you can attach to the live session).
    """
    if _store is None:
        return {"error": "store not configured"}
    if len(title) > 500:
        return {"error": "title exceeds 500 characters"}
    if len(description) > 50_000:
        return {"error": "description exceeds 50000 characters"}
    if len(type) > 64:
        return {"error": "type exceeds 64 characters"}

    task_type = type if type not in TaskType.__members__.values() else TaskType(type)
    task = Task.new(
        task_type=task_type,
        source=TaskSource.CHAT,
        title=title,
        description=description,
        repo=repo,
    )
    await _store.save(task)
    if _coordinator is not None and hasattr(_coordinator, "nudge"):
        _coordinator.nudge()
    return {"id": task.id, "status": task.status.value}


async def get_task(task_id: str) -> dict:
    """Fetch a task's full state (status, result, handler_data) by id."""
    if _store is None:
        return {"error": "store not configured"}
    task = await _store.get(task_id)
    if task is None:
        return {"error": "Task not found"}
    return task.model_dump(mode="json")


async def list_tasks(status: str | None = None, type: str | None = None) -> Any:
    """List recent tasks, optionally filtered by status and/or type. Use for
    polling dispatched work."""
    if _store is None:
        return {"error": "store not configured"}
    if status:
        try:
            target = TaskStatus(status)
        except ValueError:
            return {"error": f"invalid status: {status}"}
        tasks = await _store.list_by_status(target)
    else:
        tasks = await _store.list_all()
    if type:
        tasks = [t for t in tasks if str(t.type) == type]
    return [t.model_dump(mode="json") for t in tasks]


def build_mcp_server(settings) -> FastMCP:
    """Construct the FastMCP server, registering tools available for this
    deployment. Conditional tools (notebook, web search) are registered only
    when their backing service is configured."""
    server = FastMCP(name="forge", stateless_http=True)
    server.add_tool(dispatch_task, name="dispatch_task")
    server.add_tool(get_task, name="get_task")
    server.add_tool(list_tasks, name="list_tasks")
    return server


__all__ = ["build_mcp_server", "configure"]
