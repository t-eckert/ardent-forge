"""Agents — stage-declared task processors.

An Agent handles a specific TaskType by declaring which stages of the
triage/execute/verify/deliver pipeline it uses. The coordinator reads the
declaration and only runs the declared stages, avoiding the dead-stub
problem of the previous fixed four-method protocol.

See docs/superpowers/specs/2026-04-12-connectors-and-flexible-agents.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from forge.connectors import Tool

if TYPE_CHECKING:
    from forge.config import Settings
    from forge.models import Task
    from forge.store import TaskStore

logger = logging.getLogger(__name__)


Stage = str  # one of "triage" | "execute" | "verify" | "deliver"

_STAGE_ORDER: tuple[Stage, ...] = ("triage", "execute", "verify", "deliver")


@dataclass
class AgentContext:
    """Everything an agent needs to do its work.

    Built by the coordinator from the agent's connector declarations + the
    shared store and settings. Passed to every stage method.
    """

    tools: list[Tool]
    store: "TaskStore"
    settings: "Settings | None" = None


@runtime_checkable
class Agent(Protocol):
    """Task processor. Declares which stages it runs and which connectors it needs.

    An agent's ``stages`` list is the authoritative declaration — the coordinator
    will only call stage methods listed there. ``execute`` is required; the
    other three are optional and only used when named in ``stages``.
    """

    name: str
    task_type: str
    stages: list[Stage]
    connectors: list[str]

    async def execute(self, task: "Task", ctx: AgentContext) -> dict: ...

    # Optional — only called when declared in `stages`.
    async def triage(self, task: "Task", ctx: AgentContext) -> bool: ...
    async def verify(self, task: "Task", ctx: AgentContext) -> bool: ...
    async def deliver(self, task: "Task", ctx: AgentContext) -> dict: ...


def validate_stages(stages: list[Stage]) -> None:
    """Every stage must be one of the known names, and execute must be present."""
    unknown = [s for s in stages if s not in _STAGE_ORDER]
    if unknown:
        raise ValueError(f"Unknown stages: {unknown}")
    if "execute" not in stages:
        raise ValueError("Agent.stages must always include 'execute'")
    # Enforce canonical ordering — stages should be declared in pipeline order.
    indices = [_STAGE_ORDER.index(s) for s in stages]
    if indices != sorted(indices):
        raise ValueError(
            f"Agent.stages must be declared in pipeline order (triage → execute → verify → deliver); got {stages}"
        )


@dataclass
class AgentRegistry:
    _by_task_type: dict[str, Agent] = field(default_factory=dict)

    def register(self, agent: Agent) -> None:
        validate_stages(agent.stages)
        if agent.task_type in self._by_task_type:
            raise ValueError(f"Agent already registered for task_type: {agent.task_type}")
        self._by_task_type[agent.task_type] = agent

    def get(self, task_type: str) -> Agent | None:
        return self._by_task_type.get(task_type)

    def list(self) -> list[Agent]:
        return list(self._by_task_type.values())


__all__ = ["Agent", "AgentContext", "AgentRegistry", "Stage", "validate_stages"]
