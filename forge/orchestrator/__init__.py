"""Forge orchestrator — the single conversational identity.

Composes persona + memory + capability + context into every turn's system
prompt, decides turn shape (synchronous tool vs task dispatch), and narrates
agent completions back into their originating threads.

Phase C scope: system-prompt assembly + streaming chat routing.
Phase D+ adds thread persistence, task-dispatch turns, and resolution posting.

See docs/superpowers/specs/2026-04-13-forge-orchestrator.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, AsyncIterator

from forge.orchestrator.dispatch import TurnShape, decide_turn_shape
from forge.orchestrator.narration import narrate_resolution
from forge.orchestrator.persona import PERSONA
from forge.orchestrator.system_prompt import ThreadContext, build_system_prompt

if TYPE_CHECKING:
    from forge.agents import AgentRegistry
    from forge.connectors import ConnectorRegistry
    from forge.store import TaskStore

logger = logging.getLogger(__name__)


@dataclass
class ForgeOrchestrator:
    """Single coordinating object the chat API routes every turn through.

    Holds references to the registries + store but doesn't own any transport —
    the FastAPI endpoint is responsible for Anthropic streaming. The orchestrator
    provides the system prompt, the active tool schemas, and the turn-shape
    decision; the endpoint handles I/O.
    """

    connectors: "ConnectorRegistry"
    agents: "AgentRegistry"
    store: "TaskStore | None" = None
    # Supplied by the memory layer in Phase E. Empty until then.
    memory_index_provider: "callable[[], str] | None" = None

    def _memory_index(self) -> str | None:
        if self.memory_index_provider is None:
            return None
        try:
            return self.memory_index_provider()
        except Exception:
            logger.exception("memory_index_provider raised")
            return None

    def system_prompt(self, thread_context: ThreadContext | None = None) -> str:
        """Build the system prompt for a turn in the given context."""
        tools = self.connectors.all_tools() if self.connectors else []
        return build_system_prompt(
            memory_index=self._memory_index(),
            connectors=[c.name for c in self.connectors.all()] if self.connectors else [],
            agents=[a.task_type for a in self.agents.list()] if self.agents else [],
            tools=[t.name for t in tools],
            thread_context=thread_context,
        )

    def tool_schemas(self) -> list[dict]:
        """Anthropic-shaped tool schemas for every registered connector tool."""
        if not self.connectors:
            return []
        return [t.to_anthropic_schema() for t in self.connectors.all_tools()]

    def resolve_tool_call(self, name: str):
        """Look up a tool + decide its turn shape. Returns (tool, turn_shape)."""
        tool = self.connectors.find_tool(name) if self.connectors else None
        return tool, decide_turn_shape(tool)


__all__ = [
    "ForgeOrchestrator",
    "ThreadContext",
    "TurnShape",
    "PERSONA",
    "narrate_resolution",
    "build_system_prompt",
]
