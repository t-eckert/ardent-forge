"""Echo-agent smoke tests + AgentRegistry lookup semantics."""

import pytest

from forge.agents import AgentContext, AgentRegistry
from forge.agents.echo import EchoAgent
from forge.models import Task, TaskSource, TaskType


ctx = AgentContext(tools=[], store=None, settings=None)


@pytest.fixture
def task():
    return Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Echo test",
        description="Test the echo agent",
    )


@pytest.fixture
def registry():
    reg = AgentRegistry()
    reg.register(EchoAgent())
    return reg


async def test_echo_agent_execute(task):
    agent = EchoAgent()
    result = await agent.execute(task, ctx)
    assert "echo" in result["message"].lower()


async def test_echo_agent_declares_execute_only():
    # EchoAgent is the canonical "no-triage, no-verify, no-deliver" sample.
    assert EchoAgent.stages == ["execute"]


async def test_registry_finds_agent(registry):
    agent = registry.get("echo")
    assert agent is not None
    assert agent.task_type == "echo"


async def test_registry_returns_none_for_unknown(registry):
    assert registry.get("nonexistent") is None
