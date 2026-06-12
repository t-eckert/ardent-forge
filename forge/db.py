import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    source TEXT NOT NULL,
    source_id TEXT,
    repo TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    handler_data TEXT NOT NULL DEFAULT '{}',
    result TEXT,
    retries INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS task_logs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    task_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    cron_expr TEXT NOT NULL,
    task_type TEXT NOT NULL,
    task_template TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1,
    last_run TEXT,
    next_run TEXT NOT NULL
);

-- Threads — named conversations. One Forge voice; many threads per user.
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'chat',
    last_activity_at TEXT NOT NULL,
    unread INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- Thread messages — supersedes chat_messages. Has thread_id FK + variant
-- (text | widget | task-dispatched | task-resolved | memory-saved) + optional
-- widgets JSON payload and optional task_id for dispatch/resolve variants.
CREATE TABLE IF NOT EXISTS thread_messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    variant TEXT NOT NULL DEFAULT 'text',
    widgets TEXT NOT NULL DEFAULT '[]',
    task_id TEXT,
    tool_use_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS thread_messages_thread_id ON thread_messages (thread_id, created_at);

-- Task ↔ Thread join. Many-to-many. A task has at most one 'origin' relation
-- (drives the resolution post-back); many 'referenced' relations are fine.
CREATE TABLE IF NOT EXISTS thread_tasks (
    thread_id TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    relation TEXT NOT NULL CHECK (relation IN ('origin', 'referenced')),
    created_at TEXT NOT NULL,
    PRIMARY KEY (thread_id, task_id, relation)
);
CREATE INDEX IF NOT EXISTS thread_tasks_task_id ON thread_tasks (task_id);

-- Speed-test results — periodic download/upload measurements.
CREATE TABLE IF NOT EXISTS speedtest_results (
    id TEXT PRIMARY KEY,
    download_mbps REAL NOT NULL,
    upload_mbps REAL NOT NULL,
    ping_ms REAL NOT NULL,
    server_name TEXT,
    server_location TEXT,
    tested_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str):
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self):
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        # Idempotent column additions for DBs created before the column existed.
        # SQLite has no "ADD COLUMN IF NOT EXISTS" — swallow duplicate-column.
        for alter in (
            "ALTER TABLE thread_messages ADD COLUMN tool_use_id TEXT",
        ):
            try:
                await self._conn.execute(alter)
            except Exception:
                pass
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        if self._conn is None:
            raise RuntimeError("Database not initialized")
        cursor = await self._conn.execute(sql, params)
        await self._conn.commit()
        return cursor

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        if self._conn is None:
            raise RuntimeError("Database not initialized")
        cursor = await self._conn.execute(sql, params)
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        if self._conn is None:
            raise RuntimeError("Database not initialized")
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
