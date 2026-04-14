"""Decide whether a tool call should run synchronously in-turn or be promoted
to a Task dispatched to an agent.

First-pass heuristic: a tool with ``long_running=True`` promotes to a task.
Everything else runs synchronously. This is intentionally conservative — we
can refine with Claude-side decisions or per-call timeouts later.

See docs/superpowers/specs/2026-04-13-forge-orchestrator.md § Turn Types.
"""

from __future__ import annotations

from enum import Enum

from forge.connectors import Tool


class TurnShape(str, Enum):
    SYNCHRONOUS = "synchronous"
    TASK_DISPATCH = "task_dispatch"


def decide_turn_shape(tool: Tool | None) -> TurnShape:
    """Return the preferred shape for executing this tool call.

    A missing tool (unknown name from Claude) falls back to synchronous so
    the chat turn can surface the error in-place.
    """
    if tool is None:
        return TurnShape.SYNCHRONOUS
    if tool.long_running:
        return TurnShape.TASK_DISPATCH
    return TurnShape.SYNCHRONOUS


__all__ = ["TurnShape", "decide_turn_shape"]
