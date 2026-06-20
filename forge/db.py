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
    max_retries INTEGER NOT NULL DEFAULT 3,
    available_at TEXT,
    failure_kind TEXT,
    require_approval INTEGER NOT NULL DEFAULT 0,
    continues_task_id TEXT,
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
            "ALTER TABLE tasks ADD COLUMN max_retries INTEGER NOT NULL DEFAULT 3",
            "ALTER TABLE tasks ADD COLUMN available_at TEXT",
            "ALTER TABLE tasks ADD COLUMN failure_kind TEXT",
            "ALTER TABLE tasks ADD COLUMN require_approval INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE tasks ADD COLUMN continues_task_id TEXT",
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
