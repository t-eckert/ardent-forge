"""Connectors — encapsulated external capabilities that provide tools.

Each Connector owns its auth, config, and health. Its tools are exposed to
Forge (chat) and to any agent that declares the connector in its dependencies.

See docs/superpowers/specs/2026-04-12-connectors-and-flexible-agents.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """A self-contained capability a connector provides.

    The execute callable must be async, accept keyword args matching
    input_schema, and return a JSON-serialisable dict. On error it should
    return a dict with an "error" key rather than raise — that lets the
    caller surface the failure as a tool_result with is_error=True.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    execute: Callable[..., Awaitable[dict[str, Any]]]
    connector_name: str
    # When True, the dispatcher should prefer running this as a Task rather
    # than inline in a synchronous chat turn. First-pass heuristic; refined later.
    long_running: bool = False
    # Optional transform from raw tool result → widget payload dict for the UI.
    # Return None to skip widget emission (e.g. on error results).
    to_widget: Optional[Callable[[dict[str, Any]], dict[str, Any] | None]] = None

    def to_anthropic_schema(self) -> dict[str, Any]:
        """Emit the JSON shape Claude expects for tool_use declarations."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@runtime_checkable
class Connector(Protocol):
    name: str

    async def setup(self) -> None:
        """Initialize auth, validate config. Called once on startup."""
        ...

    async def health(self) -> bool:
        """Is this connector operational right now?"""
        ...

    @property
    def tools(self) -> list[Tool]:
        """The tools this connector provides."""
        ...


@dataclass
class ConnectorRegistry:
    _by_name: dict[str, Connector] = field(default_factory=dict)

    def register(self, connector: Connector) -> None:
        if connector.name in self._by_name:
            raise ValueError(f"Connector already registered: {connector.name}")
        self._by_name[connector.name] = connector

    def get(self, name: str) -> Connector | None:
        return self._by_name.get(name)

    def all(self) -> list[Connector]:
        return list(self._by_name.values())

    def all_tools(self) -> list[Tool]:
        """Every tool from every registered connector. Fed to Claude in chat."""
        tools: list[Tool] = []
        for c in self._by_name.values():
            tools.extend(c.tools)
        return tools

    def tools_for(self, connector_names: list[str]) -> list[Tool]:
        """Tools from the named connectors. Used by agents to request a scoped toolkit."""
        tools: list[Tool] = []
        for name in connector_names:
            c = self._by_name.get(name)
            if c is None:
                logger.warning("Agent requested unregistered connector: %s", name)
                continue
            tools.extend(c.tools)
        return tools

    def find_tool(self, tool_name: str) -> Tool | None:
        """Look up a tool across all registered connectors by name."""
        for c in self._by_name.values():
            for t in c.tools:
                if t.name == tool_name:
                    return t
        return None

    async def setup_all(self) -> None:
        """Run setup() on every connector. Failures are logged, not raised —
        a broken connector shouldn't prevent the rest of the system coming up."""
        for c in self._by_name.values():
            try:
                await c.setup()
            except Exception:
                logger.exception("Connector setup failed: %s", c.name)

    async def health_check(self) -> dict[str, bool]:
        """Aggregate health across all connectors. Used by /api/connectors/health."""
        out: dict[str, bool] = {}
        for c in self._by_name.values():
            try:
                out[c.name] = await c.health()
            except Exception:
                logger.exception("Connector health check raised: %s", c.name)
                out[c.name] = False
        return out


__all__ = ["Tool", "Connector", "ConnectorRegistry"]
