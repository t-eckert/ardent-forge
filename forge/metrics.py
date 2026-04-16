from __future__ import annotations

from typing import TYPE_CHECKING

from prometheus_client import Counter, Gauge, Histogram

if TYPE_CHECKING:
    from forge.agents import AgentRegistry
    from forge.connectors import ConnectorRegistry

# -- Task pipeline --

TASKS_TOTAL = Counter(
    "forge_tasks_total",
    "Total tasks that reached a terminal state",
    ["type", "status"],
)

TASK_DURATION_SECONDS = Histogram(
    "forge_task_duration_seconds",
    "Wall-clock time from dequeue to terminal state",
    ["type"],
    buckets=[1, 5, 15, 30, 60, 120, 300, 600, 1800],
)

TASK_STAGE_DURATION_SECONDS = Histogram(
    "forge_task_stage_duration_seconds",
    "Duration of each pipeline stage",
    ["stage"],
    buckets=[0.5, 1, 5, 15, 30, 60, 120, 300, 600],
)

QUEUE_DEPTH = Gauge(
    "forge_queue_depth",
    "Number of tasks currently in queued state",
)

ACTIVE_TASKS = Gauge(
    "forge_active_tasks",
    "Number of tasks currently being processed",
)

# -- Coordinator loop --

TICK_DURATION_SECONDS = Histogram(
    "forge_tick_duration_seconds",
    "Duration of one coordinator tick",
    buckets=[0.1, 0.5, 1, 5, 15, 30, 60],
)

TICKS_TOTAL = Counter(
    "forge_ticks_total",
    "Total coordinator ticks executed",
)

# -- External integrations --

LINEAR_POLLS_TOTAL = Counter(
    "forge_linear_polls_total",
    "Linear poll attempts",
    ["result"],
)

LINEAR_TASKS_INGESTED = Counter(
    "forge_linear_tasks_ingested_total",
    "Tasks ingested from Linear",
)

HANDLER_ERRORS_TOTAL = Counter(
    "forge_handler_errors_total",
    "Unhandled exceptions during task processing",
    ["type"],
)

# -- Orchestrator / chat --

CHAT_TURNS_TOTAL = Counter(
    "forge_chat_turns_total",
    "Chat turns handled by the orchestrator, labelled by turn shape",
    ["shape"],  # synchronous | synchronous_tool | task_dispatch | error
)

CHAT_TOOL_CALLS_TOTAL = Counter(
    "forge_chat_tool_calls_total",
    "Tool invocations triggered during a chat turn",
    ["tool", "connector", "result"],
)

CHAT_TURN_DURATION_SECONDS = Histogram(
    "forge_chat_turn_duration_seconds",
    "Wall-clock time from user message to final assistant token",
    buckets=[0.5, 1, 2, 5, 10, 20, 60],
)

RESOLUTION_POSTS_TOTAL = Counter(
    "forge_resolution_posts_total",
    "Task resolution messages posted back to origin threads",
    ["agent"],
)

# -- Connectors --

CONNECTOR_HEALTH = Gauge(
    "forge_connector_health",
    "1 if the connector's health() returned true on last check",
    ["connector"],
)

# -- Memory --

MEMORY_READS_TOTAL = Counter(
    "forge_memory_reads_total",
    "Memory index loads (once per chat turn that includes memory)",
)

MEMORY_WRITES_TOTAL = Counter(
    "forge_memory_writes_total",
    "Memory file writes — cumulative across types",
    ["type"],
)


# -- Startup priming --
#
# Prometheus counters/histograms only produce series after their first
# observation. That means dashboards show "No data" on a freshly-booted
# forge even though everything is wired correctly. To give panels something
# to render against, we touch every known label combination at startup —
# `.labels(...)` creates a zero-valued child which is exported immediately.

_TERMINAL_STATUSES = ("completed", "failed")
_PIPELINE_STAGES = ("triage", "execute", "verify", "deliver")
_CHAT_TURN_SHAPES = ("synchronous", "synchronous_tool", "task_dispatch", "error")
_LINEAR_POLL_RESULTS = ("success", "error")
_MEMORY_TYPES = ("user", "feedback", "project", "reference")
_TOOL_CALL_RESULTS = ("ok", "error")


def prime_metrics(
    agents: "AgentRegistry",
    connectors: "ConnectorRegistry",
) -> None:
    """Pre-register series for every known label combination.

    Called once on startup after both registries are populated. Keeps Grafana
    panels from reading "No data" on a freshly-booted forge — after priming,
    every metric has at least one zero-valued series in ``/metrics``.
    """
    for stage in _PIPELINE_STAGES:
        TASK_STAGE_DURATION_SECONDS.labels(stage=stage)

    for agent in agents.list():
        task_type = agent.task_type
        TASK_DURATION_SECONDS.labels(type=task_type)
        HANDLER_ERRORS_TOTAL.labels(type=task_type)
        for status in _TERMINAL_STATUSES:
            TASKS_TOTAL.labels(type=task_type, status=status)
        agent_label = getattr(agent, "name", task_type)
        RESOLUTION_POSTS_TOTAL.labels(agent=agent_label)

    for result in _LINEAR_POLL_RESULTS:
        LINEAR_POLLS_TOTAL.labels(result=result)

    for shape in _CHAT_TURN_SHAPES:
        CHAT_TURNS_TOTAL.labels(shape=shape)

    # Every real tool from every connector, plus the synthetic dispatch_task.
    for connector in connectors.all():
        CONNECTOR_HEALTH.labels(connector=connector.name).set(0)
        for tool in connector.tools:
            for result in _TOOL_CALL_RESULTS:
                CHAT_TOOL_CALLS_TOTAL.labels(
                    tool=tool.name,
                    connector=connector.name,
                    result=result,
                )
    for result in _TOOL_CALL_RESULTS:
        CHAT_TOOL_CALLS_TOTAL.labels(
            tool="dispatch_task",
            connector="orchestrator",
            result=result,
        )

    for mem_type in _MEMORY_TYPES:
        MEMORY_WRITES_TOTAL.labels(type=mem_type)
