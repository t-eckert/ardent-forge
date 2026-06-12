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


def _mem_dict(entry) -> dict:
    return {
        "filename": entry.filename,
        "slug": entry.slug,
        "name": entry.name,
        "description": entry.description,
        "type": entry.type,
        "body": entry.body,
        "updated_at": entry.updated_at,
    }


async def list_memory() -> Any:
    """List Forge's memory entries (shared with chat/Linear sessions)."""
    if _memory is None:
        return {"error": "memory not configured"}
    return [_mem_dict(e) for e in _memory.list()]


async def read_memory(filename: str) -> dict:
    """Read one memory entry, including its full body."""
    if _memory is None:
        return {"error": "memory not configured"}
    entry = _memory.get(filename)
    if entry is None:
        return {"error": f"No memory: {filename}"}
    return _mem_dict(entry)


async def write_memory(
    name: str, description: str, type: str, body: str, filename: str | None = None
) -> dict:
    """Create or update a memory entry. type is one of: user, feedback,
    project, reference. Writes regenerate MEMORY.md automatically."""
    if _memory is None:
        return {"error": "memory not configured"}
    if type not in VALID_TYPES:
        return {"error": f"invalid type: {type}; must be one of {', '.join(VALID_TYPES)}"}
    try:
        entry = _memory.write(
            name=name, description=description, type=type, body=body, filename=filename
        )
    except ValueError as exc:
        return {"error": str(exc)}
    return _mem_dict(entry)


async def delete_memory(filename: str) -> dict:
    """Delete a memory entry by filename."""
    if _memory is None:
        return {"error": "memory not configured"}
    if _memory.remove(filename):
        return {"deleted": filename}
    return {"error": f"No memory: {filename}"}


async def list_repos() -> Any:
    """List workspace repos scanned from the workspace directory."""
    if _repo_registry is None:
        return {"error": "repo registry not configured"}
    return [r.model_dump(mode="json") for r in _repo_registry.list()]


async def get_repo(name: str) -> dict:
    """Fetch a single workspace repo by name (relative path from workspace root)."""
    if _repo_registry is None:
        return {"error": "repo registry not configured"}
    repo = _repo_registry.get(name)
    if repo is None:
        return {"error": f"Repo not found: {name}"}
    return repo.model_dump(mode="json")


async def clone_repo(url: str) -> dict:
    """Clone a git repo into the workspace using the host/owner/repo directory layout.

    Accepts any of: https://github.com/owner/repo, git@github.com:owner/repo,
    or bare owner/repo shorthand (defaults to github.com). If the destination
    already exists it is registered without re-cloning. Returns the Repo on
    success or an error dict."""
    if _repo_registry is None:
        return {"error": "repo registry not configured"}
    try:
        repo = await _repo_registry.clone(url)
        return repo.model_dump(mode="json")
    except (ValueError, RuntimeError) as exc:
        return {"error": str(exc)}


async def list_schedules() -> Any:
    """List cron schedules that fire Forge tasks."""
    if _store is None:
        return {"error": "store not configured"}
    return await _store.list_schedules()


async def create_schedule(
    name: str,
    cron_expr: str,
    task_type: str,
    repo: str | None = None,
    prompt_template: str | None = None,
    label: str | None = None,
) -> dict:
    """Create a cron schedule. cron_expr is standard 5-field cron. For Code
    tasks, repo is GitHub owner/name and prompt_template becomes the task
    description on each fire."""
    if _store is None:
        return {"error": "store not configured"}
    template: dict = {}
    if repo:
        template["repo"] = repo
    if prompt_template:
        template["description"] = prompt_template
    if label:
        template["label"] = label
    if prompt_template and not template.get("title"):
        template["title"] = prompt_template.splitlines()[0][:120]
    try:
        schedule_id = await _store.save_schedule(
            name=name, cron_expr=cron_expr, task_type=task_type, task_template=template
        )
    except ValueError as exc:
        return {"error": f"invalid cron expression '{cron_expr}': {exc}"}
    return await _store.get_schedule(schedule_id)


async def delete_schedule(schedule_id: str) -> dict:
    """Delete a cron schedule by id."""
    if _store is None:
        return {"error": "store not configured"}
    if await _store.get_schedule(schedule_id) is None:
        return {"error": "Schedule not found"}
    await _store.delete_schedule(schedule_id)
    return {"deleted": schedule_id}


async def search_notebook(query: str) -> Any:
    """Full-text search the read-only Obsidian notebook. Returns matching
    file paths, line numbers, and lines."""
    if _notebook_reader is None:
        return {"error": "notebook not configured"}
    return [
        {"path": h.path, "line_number": h.line_number, "line": h.line}
        for h in _notebook_reader.search(query)
    ]


async def read_note(path: str) -> dict:
    """Read a note from the read-only notebook by vault-relative path."""
    if _notebook_reader is None:
        return {"error": "notebook not configured"}
    try:
        return {"path": path, "content": _notebook_reader.read(path)}
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}


async def web_search(query: str, max_results: int = 5) -> dict:
    """Search the web for current information via Forge's web-search connector."""
    tool = _connectors.find_tool("web_search") if _connectors is not None else None
    if tool is None:
        return {"error": "web search not configured"}
    return await tool.execute(query=query, max_results=max_results)


def build_mcp_server(settings) -> FastMCP:
    """Construct the FastMCP server, registering tools available for this
    deployment. Conditional tools (notebook, web search) are registered only
    when their backing service is configured."""
    # streamable_http_path="/" so that when the app is mounted at "/mcp" in
    # main.py, the endpoint is exactly "/mcp" (the default "/mcp" path would
    # land the route at "/mcp/mcp" under the mount). Requests to "/mcp" are
    # 307-redirected to "/mcp/", which MCP clients follow.
    server = FastMCP(name="forge", stateless_http=True, streamable_http_path="/")
    server.add_tool(dispatch_task, name="dispatch_task")
    server.add_tool(get_task, name="get_task")
    server.add_tool(list_tasks, name="list_tasks")
    server.add_tool(list_memory, name="list_memory")
    server.add_tool(read_memory, name="read_memory")
    server.add_tool(write_memory, name="write_memory")
    server.add_tool(delete_memory, name="delete_memory")
    server.add_tool(list_repos, name="list_repos")
    server.add_tool(get_repo, name="get_repo")
    server.add_tool(clone_repo, name="clone_repo")
    server.add_tool(list_schedules, name="list_schedules")
    server.add_tool(create_schedule, name="create_schedule")
    server.add_tool(delete_schedule, name="delete_schedule")

    if Path(settings.notebook_dir).is_dir():
        server.add_tool(search_notebook, name="search_notebook")
        server.add_tool(read_note, name="read_note")

    if settings.tavily_api_key:
        server.add_tool(web_search, name="web_search")

    return server


__all__ = ["build_mcp_server", "configure"]
