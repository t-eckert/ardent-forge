---
status: ready-to-plan
title: Connectors and flexible agents
---

# Connectors and Flexible Agents — Design Spec

**Date:** 2026-04-12

## Context

Ardent Forge's architecture has two structural pressures:

1. **The task pipeline is rigid.** Every `TaskHandler` must implement `triage → execute → verify → deliver`, even when stages are meaningless. The `ResearchHandler.deliver` returns an empty dict. `TicketsHandler.triage` always returns True. `EchoHandler` implements all four as trivial stubs. As we add agents for personal data (Strava, YNAB), scheduled briefings, and chat-oriented workflows, this friction compounds — some agents are one-shot, some are reactive, some are continuous. The protocol forces them all through the same state machine with dead stages.

2. **Tools have no encapsulation.** The weather tool is a bare function + JSON schema, imported directly in `chat.py`. There's no concept of "the weather service has auth, health, and multiple capabilities." As we add web search, Strava, YNAB, Linear read-back, notebook access, and more, each tool would be another ad-hoc import with its own config scattered across the codebase. Agents that need tools (a morning briefing needs weather + calendar + tasks) have no way to declare or receive them.

This spec addresses both by introducing **Connectors** (encapsulated external capabilities that provide tools) and **flexible agent pipelines** (agents declare which stages they need rather than implementing a fixed four-step protocol).

## Design: Connectors

A Connector encapsulates a single external service or capability. It manages its own configuration, authentication, and health, and exposes one or more tools that agents and the chat system can use.

### Connector Protocol

```python
class Connector(Protocol):
    name: str                          # "weather", "strava", "ynab"
    
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
```

### Tool Definition

Each tool is a self-contained unit: schema for Claude, implementation function, and a reference back to its parent connector.

```python
@dataclass
class Tool:
    name: str                          # "get_weather", "get_strava_activities"
    description: str                   # Human/Claude-readable
    input_schema: dict                 # JSON Schema for Claude tool_use
    execute: Callable[..., Awaitable[dict]]  # The implementation
    connector_name: str                # Which connector owns this
```

### Connector Registry

```python
class ConnectorRegistry:
    def register(self, connector: Connector) -> None
    def get(self, name: str) -> Connector | None
    def all_tools(self) -> list[Tool]
    def tools_for(self, connector_names: list[str]) -> list[Tool]
    def health_check(self) -> dict[str, bool]
```

`all_tools()` returns every tool from every registered connector — this is what `chat.py` passes to Claude. `tools_for()` returns a subset — this is what agents use when they declare their dependencies.

### Example: Weather Connector

The existing `forge/tools/weather.py` becomes:

```python
class WeatherConnector:
    name = "weather"

    def __init__(self, base_url: str = "http://127.0.0.1:8091"):
        self._base_url = base_url

    async def setup(self) -> None:
        pass  # No auth needed — The Weather service is local

    async def health(self) -> bool:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{self._base_url}/")
            return resp.status_code < 500

    @property
    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="get_weather",
                description="Get current weather and 8-day forecast...",
                input_schema={...},
                execute=self._get_weather,
                connector_name=self.name,
            )
        ]

    async def _get_weather(self, location: str | None = None) -> dict:
        # ... existing get_weather logic, unchanged
```

### Example: Future Strava Connector

```python
class StravaConnector:
    name = "strava"

    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self._client_id = client_id
        # ... OAuth config from 1Password

    async def setup(self) -> None:
        self._access_token = await self._refresh_oauth()

    async def health(self) -> bool:
        return self._access_token is not None

    @property
    def tools(self) -> list[Tool]:
        return [
            Tool(name="get_strava_activities", ...),
            Tool(name="get_strava_stats", ...),
        ]
```

### Chat Integration

`chat.py` changes from importing specific tools to pulling from the registry:

```python
# Before:
from forge.tools.weather import WEATHER_TOOL_SCHEMA, get_weather
tools = [WEATHER_TOOL_SCHEMA]
# ... hardcoded dispatch: if block.name == "get_weather": ...

# After:
tools = connector_registry.all_tools()
tool_schemas = [t.to_schema() for t in tools]
# ... generic dispatch:
tool = connector_registry.find_tool(block.name)
result = await tool.execute(**block.input)
```

No more per-tool if/else chain. Adding a connector automatically makes its tools available in chat.

### Startup

Connectors are created and registered in `main.py` lifespan, same as handlers today:

```python
connector_registry = ConnectorRegistry()
connector_registry.register(WeatherConnector(base_url=...))
# connector_registry.register(StravaConnector(...))  # future
# connector_registry.register(YNABConnector(...))    # future
await connector_registry.setup_all()
```

## Design: Flexible Agent Pipelines

### Problem

The current `TaskHandler` protocol mandates four stages. The coordinator hardcodes the sequence: triage → execute → verify → deliver. Every handler must implement all four, even as no-ops.

This doesn't just mean dead code — it means the state machine records meaningless transitions (a research task "verifying" when there's nothing to verify), metrics track empty stages, and new handler authors must understand and stub out stages that don't apply.

### Approach: Agents Declare Their Stages

Replace the fixed four-method protocol with an agent that declares which stages it uses. The coordinator reads this declaration and only runs those stages.

```python
class Agent(Protocol):
    name: str                          # "code", "research", "plan", etc.
    task_type: str                     # Maps to TaskType enum
    stages: list[str]                  # e.g., ["execute"] or ["triage", "execute", "verify", "deliver"]
    connectors: list[str]              # e.g., ["weather", "strava"] — which connectors this agent needs

    async def execute(self, task: Task, ctx: AgentContext) -> dict:
        """Required. Every agent does some work."""
        ...

    # Optional — only required if declared in stages:
    async def triage(self, task: Task, ctx: AgentContext) -> bool: ...
    async def verify(self, task: Task, ctx: AgentContext) -> bool: ...
    async def deliver(self, task: Task, ctx: AgentContext) -> dict: ...
```

### AgentContext

Instead of agents reaching into global state or receiving dependencies through `__init__`, the coordinator passes an `AgentContext` with everything the agent needs:

```python
@dataclass
class AgentContext:
    tools: list[Tool]                  # Resolved from agent's connector declarations
    store: TaskStore                   # For reading related data
    settings: Settings                 # Config access
```

The coordinator builds this from the agent's `connectors` declaration:

```python
tools = connector_registry.tools_for(agent.connectors)
ctx = AgentContext(tools=tools, store=store, settings=settings)
```

### Coordinator Changes

The coordinator loop becomes stage-aware:

```python
async def process_task(self, task, agent):
    ctx = self._build_context(agent)

    if "triage" in agent.stages:
        await self._store.update_status(task.id, TaskStatus.TRIAGING)
        if not await agent.triage(task, ctx):
            await self._store.mark_failed(task.id, error="Declined during triage")
            return

    await self._store.update_status(task.id, TaskStatus.EXECUTING)
    result = await agent.execute(task, ctx)
    await self._store.update_handler_data(task.id, result)
    task = await self._store.get(task.id)

    if "verify" in agent.stages:
        await self._store.update_status(task.id, TaskStatus.VERIFYING)
        if not await agent.verify(task, ctx):
            await self._store.mark_failed(task.id, error="Verification failed")
            return

    if "deliver" in agent.stages:
        await self._store.update_status(task.id, TaskStatus.DELIVERING)
        delivery = await agent.deliver(task, ctx)
        result = {**result, **delivery}

    await self._store.mark_completed(task.id, result)
```

The state machine still records which stages ran — but only the ones that actually ran.

### Agent Registry

Replaces `HandlerRegistry`:

```python
class AgentRegistry:
    def register(self, agent: Agent) -> None
    def get(self, task_type: str) -> Agent | None
    def list(self) -> list[Agent]
```

### Existing Handlers → Agents

Each current handler maps cleanly:

| Handler | Stages | Connectors |
|---------|--------|------------|
| CodeHandler → CodeAgent | `["triage", "execute", "verify", "deliver"]` | `["github"]` |
| PlanHandler → PlanAgent | `["execute", "verify", "deliver"]` | `["github"]` |
| ResearchHandler → ResearchAgent | `["execute", "verify"]` | `["websearch", "notebook"]` |
| TicketsHandler → TicketsAgent | `["execute", "deliver"]` | `["linear"]` |
| EchoHandler → EchoAgent | `["execute"]` | `[]` |

### Future Agents Enabled by This Design

| Agent | Stages | Connectors | Notes |
|-------|--------|------------|-------|
| MorningBriefing | `["execute"]` | `["weather", "strava", "linear", "notebook"]` | Scheduled, pulls data from multiple connectors, writes summary |
| BudgetCheck | `["execute", "deliver"]` | `["ynab", "notebook"]` | Scheduled weekly, deliver writes to notebook |
| FitnessReport | `["execute"]` | `["strava", "notebook"]` | Weekly digest |
| WebResearch | `["execute"]` | `["websearch"]` | Ad-hoc from chat |

## What Changes, What Doesn't

### Unchanged

- **Task model** — `Task`, `TaskStatus`, `TaskType`, `TaskSource` stay as-is. Tasks are still the unit of work.
- **TaskStore** — Persistence layer is unaffected.
- **State machine** — `state.py` transitions still work; the coordinator just skips states the agent doesn't declare. We may want to allow `QUEUED → EXECUTING` as a valid transition for agents without triage.
- **Coordinator loop** — Still polls, still runs watchers, still processes pending tasks. The inner `process_pending` changes to be stage-aware.
- **Watchers and pollers** — Still create tasks. They don't care how tasks are processed.
- **Metrics** — Stage duration metrics still work since stage labels come from what actually ran.
- **Guardrails** — Still enforced per-agent. Could move to a `guardrails` field on the agent declaration.

### Changed

- **`TaskHandler` protocol → `Agent` protocol** — New protocol with `stages`, `connectors`, `AgentContext`.
- **`HandlerRegistry` → `AgentRegistry`** — Same structure, renamed for clarity.
- **`forge/tools/` → `forge/connectors/`** — Weather becomes a connector. Future services go here.
- **`chat.py` tool dispatch** — Pulls tools from `ConnectorRegistry` instead of hard-coded imports.
- **`coordinator.py` inner loop** — Stage-aware processing as described above.
- **`main.py` lifespan** — Creates `ConnectorRegistry`, registers connectors, passes to agents.

## File Layout

```
forge/
├── connectors/
│   ├── __init__.py          # Connector protocol, Tool dataclass, ConnectorRegistry
│   └── weather.py           # WeatherConnector (migrated from tools/)
├── agents/
│   ├── __init__.py          # Agent protocol, AgentRegistry, AgentContext
│   ├── code.py              # CodeAgent (migrated from handlers/code.py)
│   ├── plan.py              # PlanAgent
│   ├── research.py          # ResearchAgent
│   ├── tickets.py           # TicketsAgent
│   └── echo.py              # EchoAgent
├── coordinator.py           # Updated for stage-aware processing
├── api/
│   └── chat.py              # Updated for ConnectorRegistry tool dispatch
└── ...
```

## Migration Path

This is a refactor of internal structure, not a feature addition. The external API, UI, task model, and database schema are unchanged. Migration is:

1. Add `forge/connectors/__init__.py` with protocol, dataclass, registry.
2. Migrate `forge/tools/weather.py` → `forge/connectors/weather.py` as `WeatherConnector`.
3. Add `forge/agents/__init__.py` with protocol, registry, context.
4. Migrate each handler from `forge/handlers/` → `forge/agents/`, adding `stages` and `connectors` declarations.
5. Update `coordinator.py` for stage-aware processing.
6. Update `chat.py` to pull tools from `ConnectorRegistry`.
7. Update `main.py` lifespan to wire everything together.
8. Update `state.py` to allow skipping stages (e.g., `QUEUED → EXECUTING`).
9. Delete `forge/handlers/` and `forge/tools/`.

Each step is independently testable. Existing tests continue to pass at each step since behavior is preserved.

## Success Criteria

- All existing task types work identically — same behavior, same PR output, same notebook writes.
- Adding a new connector (e.g., stub Strava) requires one file in `forge/connectors/`, one registration line in `main.py`, and zero changes to `chat.py` or the coordinator.
- Adding a new agent requires one file in `forge/agents/`, one registration line in `main.py`, and the agent only implements the stages it uses.
- Chat tool dispatch has no per-tool branching — it's fully generic through the registry.
- `GET /health` (or a new endpoint) can report connector health status.

## Out of Scope

- **Connector auth refresh loops.** Connectors with OAuth (Strava, YNAB) will need token refresh. The `setup()` method handles initial auth; refresh strategy is per-connector and will be designed when those connectors are built.
- **Dynamic connector loading.** Connectors are registered in code at startup. No hot-loading or plugin system.
- **Tool permissions.** All tools are available to all agents that declare the connector. Per-tool access control is not needed for a single-user system.
- **Agent-to-agent orchestration.** An agent that spawns sub-tasks for other agents (e.g., a "morning briefing" that dispatches a weather lookup and a task summary) is a natural next step but not part of this spec.
- **Chat connector selection.** Chat gets all tools from all connectors. A future enhancement could let the user scope which connectors are active in chat.
