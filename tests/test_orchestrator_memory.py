"""A memory written via MemoryStore shows up in the orchestrator's system prompt."""

from pathlib import Path

import pytest

from forge.agents import AgentRegistry
from forge.connectors import ConnectorRegistry
from forge.memory import MemoryStore
from forge.orchestrator import ForgeOrchestrator


@pytest.fixture
def orchestrator(tmp_path: Path):
    return ForgeOrchestrator(
        connectors=ConnectorRegistry(),
        agents=AgentRegistry(),
        memory=MemoryStore(tmp_path),
    )


def test_empty_memory_produces_placeholder_line(orchestrator):
    prompt = orchestrator.system_prompt()
    assert "## Memory" in prompt
    # Empty store → builder emits the "(none yet — …)" placeholder.
    assert "(none yet" in prompt


def test_memory_write_flows_into_system_prompt(orchestrator):
    orchestrator.memory.write(
        name="User role",
        description="Software engineer at Redpanda, currently building Ardent Forge",
        type="user",
        body="Prefers concise editorial voice; Svelte 5 runes only.",
    )
    prompt = orchestrator.system_prompt()
    assert "## Memory" in prompt
    assert "## user" in prompt
    assert "User role" in prompt
    assert "Redpanda" in prompt
    # Placeholder text goes away once entries exist.
    assert "(none yet" not in prompt


def test_multiple_types_preserve_order(orchestrator):
    orchestrator.memory.write(
        name="Numbers mono",
        description="style rule",
        type="feedback",
        body="Every numeric value renders in JetBrains Mono.",
    )
    orchestrator.memory.write(
        name="User role",
        description="what user does",
        type="user",
        body="...",
    )
    prompt = orchestrator.system_prompt()
    # user bucket appears before feedback bucket because of canonical order.
    assert prompt.index("## user") < prompt.index("## feedback")
