"""Tests for the Forge orchestrator: persona, system prompt, dispatch, narration."""

import pytest

from forge.agents import AgentRegistry
from forge.agents.echo import EchoAgent
from forge.connectors import ConnectorRegistry, Tool
from forge.orchestrator import (
    ForgeOrchestrator,
    PERSONA,
    ThreadContext,
    TurnShape,
    build_system_prompt,
    narrate_resolution,
)
from forge.orchestrator.dispatch import decide_turn_shape


# ─── Persona ────────────────────────────────────────────────────────────────


def test_persona_names_the_three_principles():
    assert "One voice" in PERSONA
    assert "Choose the right turn shape" in PERSONA
    assert "Learn durably, act lightly" in PERSONA
    assert "Ardent Forge" in PERSONA


def test_persona_forbids_narration_bypass():
    # The single-voice rule is the load-bearing constraint — it must be explicit.
    assert "agents never speak directly" in PERSONA.lower()


# ─── System prompt assembly ─────────────────────────────────────────────────


def test_system_prompt_includes_every_layer():
    prompt = build_system_prompt(
        memory_index="- [User role](user.md)",
        connectors=["weather", "github"],
        agents=["code", "echo"],
        tools=["get_weather", "create_pr"],
        thread_context=ThreadContext(
            tool_profile="code+tools",
            field_scope="Health",
            now_iso="2026-04-13T14:00:00Z",
        ),
    )
    assert PERSONA.strip().split("\n", 1)[0] in prompt
    assert "## Memory" in prompt
    assert "[User role]" in prompt
    assert "## Capabilities" in prompt
    # Capability lists are sorted for stability across the prompt build.
    assert "github, weather" in prompt
    assert "code, echo" in prompt
    assert "create_pr, get_weather" in prompt
    assert "## Context" in prompt
    assert "code+tools" in prompt
    assert "Health" in prompt
    assert "2026-04-13T14:00:00Z" in prompt


def test_system_prompt_omits_empty_context_block():
    prompt = build_system_prompt()
    assert "## Context" not in prompt


def test_system_prompt_handles_empty_capabilities():
    prompt = build_system_prompt()
    assert "Connectors: none registered" in prompt
    assert "Agents: none registered" in prompt


# ─── Dispatch heuristic ─────────────────────────────────────────────────────


def _tool(name: str, *, long_running: bool = False) -> Tool:
    async def _run(**kw):
        return {}

    return Tool(
        name=name,
        description="",
        input_schema={"type": "object", "properties": {}},
        execute=_run,
        connector_name="x",
        long_running=long_running,
    )


def test_dispatch_short_tool_is_synchronous():
    assert decide_turn_shape(_tool("get_weather")) is TurnShape.SYNCHRONOUS


def test_dispatch_long_running_tool_promotes_to_task():
    assert (
        decide_turn_shape(_tool("run_agent", long_running=True)) is TurnShape.TASK_DISPATCH
    )


def test_dispatch_unknown_tool_falls_back_synchronous():
    # Unknown tool surfaces in the chat turn as an error; no task dispatch.
    assert decide_turn_shape(None) is TurnShape.SYNCHRONOUS


# ─── Narration ──────────────────────────────────────────────────────────────


def test_narration_reports_pr_url():
    line = narrate_resolution(
        "code-agent",
        "Rename tClient",
        {"pr_url": "https://github.com/foo/bar/pull/247", "branch": "forge/xyz"},
    )
    assert "code-agent" in line
    assert "rename tclient" in line.lower()
    assert "https://github.com/foo/bar/pull/247" in line


def test_narration_reports_issue_count():
    line = narrate_resolution(
        "tickets-agent", "Plan connectors", {"issue_count": 7}
    )
    assert "7 issues created" in line


def test_narration_notes_error():
    line = narrate_resolution("code-agent", "Broken run", {"error": "build failed"})
    assert "build failed" in line


# ─── Orchestrator façade ────────────────────────────────────────────────────


async def _fake_search(**kwargs):
    return {"results": []}


@pytest.fixture
def wired_orchestrator():
    connectors = ConnectorRegistry()
    fake_tool = Tool(
        name="web_search",
        description="Search the web for information.",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        execute=_fake_search,
        connector_name="search",
    )

    class FakeSearchConnector:
        name = "search"
        async def setup(self): pass
        async def health(self): return True
        @property
        def tools(self): return [fake_tool]

    connectors.register(FakeSearchConnector())
    agents = AgentRegistry()
    agents.register(EchoAgent())
    return ForgeOrchestrator(connectors=connectors, agents=agents)


def test_orchestrator_system_prompt_reflects_registries(wired_orchestrator):
    prompt = wired_orchestrator.system_prompt()
    assert "search" in prompt
    assert "echo" in prompt
    assert "web_search" in prompt


def test_orchestrator_tool_schemas_shape(wired_orchestrator):
    schemas = wired_orchestrator.tool_schemas()
    # One connector tool (web_search) + the synthetic dispatch_task meta-tool.
    by_name = {s["name"]: s for s in schemas}
    assert "web_search" in by_name
    assert "dispatch_task" in by_name
    assert set(by_name["web_search"].keys()) == {"name", "description", "input_schema"}
    # dispatch_task enumerates known agent task_types.
    assert by_name["dispatch_task"]["input_schema"]["properties"]["task_type"]["enum"] == ["echo"]


def test_orchestrator_resolve_tool_call(wired_orchestrator):
    tool, shape = wired_orchestrator.resolve_tool_call("web_search")
    assert tool is not None
    assert shape is TurnShape.SYNCHRONOUS

    tool, shape = wired_orchestrator.resolve_tool_call("nope")
    assert tool is None
    assert shape is TurnShape.SYNCHRONOUS
