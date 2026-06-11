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


def build_mcp_server(settings) -> FastMCP:
    """Construct the FastMCP server, registering tools available for this
    deployment. Conditional tools (notebook, web search) are registered only
    when their backing service is configured."""
    server = FastMCP(name="forge", stateless_http=True)
    return server


__all__ = ["build_mcp_server", "configure"]
