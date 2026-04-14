from prometheus_client import Counter, Gauge, Histogram

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
    ["shape"],  # synchronous | task_dispatch | task_resolution | error
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
