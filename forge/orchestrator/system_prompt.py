"""Assembles Forge's system prompt from five layered blocks.

Layers (in order):
  1. persona    — static voice + principles (forge/orchestrator/persona.py)
  2. memory     — preloaded MEMORY.md index, if any (Phase E wires this)
  3. capability — registered connectors (roster) + agents (roster)
  4. context    — thread-level metadata (tool profile, field scope, current time)
  5. history    — carried separately on the messages list, not in system

The composer returns only the system prompt. History is attached by the caller.

See docs/superpowers/specs/2026-04-13-forge-orchestrator.md § System Prompt Assembly.
"""

from __future__ import annotations

from dataclasses import dataclass

from forge.orchestrator.persona import PERSONA


@dataclass
class ThreadContext:
    """Per-turn metadata the orchestrator weaves into the prompt."""

    tool_profile: str | None = None  # e.g. "code+tools"
    field_scope: str | None = None   # e.g. "Health", when inside a Field
    now_iso: str | None = None


def _memory_block(memory_index: str | None) -> str:
    if not memory_index:
        return "## Memory\n\n(none yet — write one when you learn something stable)"
    return f"## Memory\n\n{memory_index.strip()}"


def _capability_block(
    connector_names: list[str],
    agent_names: list[str],
    tool_names: list[str],
) -> str:
    lines = ["## Capabilities"]
    if connector_names:
        lines.append("Connectors: " + ", ".join(sorted(connector_names)))
    else:
        lines.append("Connectors: none registered")
    if tool_names:
        lines.append("Tools: " + ", ".join(sorted(tool_names)))
        lines.append(
            "When a registered tool can answer the question, ALWAYS call it rather than "
            "answering from training data. For example, call get_weather for any weather "
            "question; call web_search for current events or recent information. The user "
            "expects live data, not stale knowledge."
        )
    if agent_names:
        lines.append("Agents (task types you can dispatch): " + ", ".join(sorted(agent_names)))
    else:
        lines.append("Agents: none registered")
    return "\n".join(lines)


def _context_block(ctx: ThreadContext | None) -> str:
    if ctx is None:
        return ""
    parts = ["## Context"]
    if ctx.now_iso:
        parts.append(f"Now: {ctx.now_iso}")
    if ctx.tool_profile:
        parts.append(f"Tool profile: {ctx.tool_profile}")
    if ctx.field_scope:
        parts.append(f"Field scope: {ctx.field_scope}")
    return "\n".join(parts) if len(parts) > 1 else ""


def build_system_prompt(
    memory_index: str | None = None,
    notebook_context: str | None = None,
    connectors: list[str] | None = None,
    agents: list[str] | None = None,
    tools: list[str] | None = None,
    thread_context: ThreadContext | None = None,
) -> str:
    """Assemble the full system prompt. Blocks with no content are omitted cleanly."""
    blocks: list[str] = [PERSONA.strip(), _memory_block(memory_index)]
    if notebook_context:
        blocks.append(notebook_context)
    blocks.append(_capability_block(connectors or [], agents or [], tools or []))
    ctx = _context_block(thread_context)
    if ctx:
        blocks.append(ctx)
    return "\n\n".join(blocks)


__all__ = ["ThreadContext", "build_system_prompt"]
