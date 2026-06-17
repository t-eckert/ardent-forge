"""Tests for the Agent primitives: stage validation + AgentRegistry semantics."""

import pytest

from forge.agents import Agent, AgentContext, AgentRegistry, validate_stages


class _Exec:
    name = "exec"
    task_type = "exec"
    stages = ["execute"]
    connectors: list[str] = []
    timeout_seconds = 60

    async def execute(self, task, ctx):
        return {"ok": True}


class _Full:
    name = "full"
    task_type = "full"
    stages = ["triage", "execute", "verify", "deliver"]
    connectors = ["weather"]
    timeout_seconds = 60

    async def triage(self, task, ctx):
        return True

    async def execute(self, task, ctx):
        return {}

    async def verify(self, task, ctx):
        return True

    async def deliver(self, task, ctx):
        return {"status": "delivered"}


def test_validate_stages_accepts_execute_only():
    validate_stages(["execute"])


def test_validate_stages_accepts_full_pipeline():
    validate_stages(["triage", "execute", "verify", "deliver"])


def test_validate_stages_requires_execute():
    with pytest.raises(ValueError, match="must always include 'execute'"):
        validate_stages(["triage", "verify"])


def test_validate_stages_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown stages"):
        validate_stages(["execute", "bogus"])


def test_validate_stages_enforces_ordering():
    with pytest.raises(ValueError, match="pipeline order"):
        validate_stages(["execute", "triage"])


def test_registry_register_and_get():
    reg = AgentRegistry()
    a = _Exec()
    reg.register(a)
    assert reg.get("exec") is a
    assert reg.get("missing") is None


def test_registry_duplicate_task_type_raises():
    reg = AgentRegistry()
    reg.register(_Exec())
    with pytest.raises(ValueError):
        reg.register(_Exec())


def test_registry_rejects_invalid_stages():
    class Bad:
        name = "bad"
        task_type = "bad"
        stages = ["verify"]  # missing execute
        connectors: list[str] = []
        timeout_seconds = 60

        async def execute(self, task, ctx):
            return {}

    reg = AgentRegistry()
    with pytest.raises(ValueError):
        reg.register(Bad())


def test_full_agent_is_runtime_checkable():
    # Agents that implement every optional method satisfy the full Protocol.
    # Execute-only agents don't; that's expected and why `stages` drives dispatch,
    # not isinstance() checks.
    assert isinstance(_Full(), Agent)


def test_agents_declare_timeout_seconds():
    from forge.agents.echo import EchoAgent
    from forge.agents.code import CodeAgent

    assert EchoAgent().timeout_seconds == 60
    assert CodeAgent().timeout_seconds == 3600
