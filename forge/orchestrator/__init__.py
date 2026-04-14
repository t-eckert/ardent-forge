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
    from forge.memory import MemoryStore
    from forge.models import Task
    from forge.store import TaskStore
    from forge.thread_store import ThreadMessage, ThreadStore

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
    thread_store: "ThreadStore | None" = None
    memory: "MemoryStore | None" = None

    def _memory_index(self) -> str | None:
        if self.memory is None:
            return None
        try:
            idx = self.memory.read_index()
        except Exception:
            logger.exception("memory.read_index raised")
            return None
        try:
            from forge.metrics import MEMORY_READS_TOTAL
            MEMORY_READS_TOTAL.inc()
        except Exception:
            pass
        return idx or None

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

    async def post_resolution(
        self,
        *,
        task: "Task",
        result: dict,
    ) -> "ThreadMessage | None":
        """If this task has an origin thread, post a resolution message to it.

        The message is authored by Forge (role='assistant'), with variant
        'task-resolved' and a narration produced by narrate_resolution(). The
        task's final handler_data is attached as a widget payload so the UI can
        embed the artifact inline.

        Returns the persisted ThreadMessage, or None if the task had no origin
        thread or the thread_store is not wired.
        """
        if self.thread_store is None:
            return None
        thread_id = await self.thread_store.origin_thread_for(task.id)
        if thread_id is None:
            return None

        agent = self.agents.get(task.type) if self.agents else None
        agent_label = getattr(agent, "name", task.type)

        narration = narrate_resolution(agent_label, task.title, result or {})

        msg = await self.thread_store.append_message(
            thread_id=thread_id,
            role="assistant",
            content=narration,
            variant="task-resolved",
            widgets=[result] if result else [],
            task_id=task.id,
        )
        await self.thread_store.mark_activity(thread_id, unread=True)
        try:
            from forge.metrics import RESOLUTION_POSTS_TOTAL
            RESOLUTION_POSTS_TOTAL.labels(agent=agent_label).inc()
        except Exception:
            pass
        return msg


__all__ = [
    "ForgeOrchestrator",
    "ThreadContext",
    "TurnShape",
    "PERSONA",
    "narrate_resolution",
    "build_system_prompt",
]
