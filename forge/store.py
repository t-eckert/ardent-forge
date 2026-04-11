import json
from datetime import datetime, timezone

from forge.db import Database
from forge.models import Task, TaskStatus


class TaskStore:
    def __init__(self, db: Database):
        self._db = db

    async def save(self, task: Task):
        row = task.to_row()
        columns = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        await self._db.execute(
            f"INSERT INTO tasks ({columns}) VALUES ({placeholders})",
            tuple(row.values()),
        )

    async def get(self, task_id: str) -> Task | None:
        row = await self._db.fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if row is None:
            return None
        return Task.from_row(row)

    async def update_status(self, task_id: str, status: TaskStatus):
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, now, task_id),
        )

    async def list_all(self, limit: int = 100) -> list[Task]:
        rows = await self._db.fetch_all(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [Task.from_row(row) for row in rows]

    async def list_by_status(self, status: TaskStatus) -> list[Task]:
        rows = await self._db.fetch_all(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at ASC",
            (status.value,),
        )
        return [Task.from_row(row) for row in rows]

    async def list_pending(self, limit: int = 10) -> list[Task]:
        rows = await self._db.fetch_all(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at ASC LIMIT ?",
            (TaskStatus.QUEUED.value, limit),
        )
        return [Task.from_row(row) for row in rows]

    async def mark_completed(self, task_id: str, result: dict):
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "UPDATE tasks SET status = ?, result = ?, completed_at = ?, updated_at = ? WHERE id = ?",
            (TaskStatus.COMPLETED.value, json.dumps(result), now, now, task_id),
        )

    async def reset_active_tasks(self) -> int:
        """Reset any tasks stuck in active (non-terminal) states back to queued.
        Called on startup to recover from unclean shutdown."""
        now = datetime.now(timezone.utc).isoformat()
        active_states = (
            TaskStatus.TRIAGING.value,
            TaskStatus.EXECUTING.value,
            TaskStatus.VERIFYING.value,
            TaskStatus.DELIVERING.value,
        )
        placeholders = ", ".join("?" for _ in active_states)
        cursor = await self._db.execute(
            f"UPDATE tasks SET status = ?, updated_at = ? WHERE status IN ({placeholders})",
            (TaskStatus.QUEUED.value, now, *active_states),
        )
        return cursor.rowcount

    async def update_handler_data(self, task_id: str, data: dict):
        now = datetime.now(timezone.utc).isoformat()
        task = await self.get(task_id)
        if task is None:
            return
        merged = {**task.handler_data, **data}
        await self._db.execute(
            "UPDATE tasks SET handler_data = ?, updated_at = ? WHERE id = ?",
            (json.dumps(merged), now, task_id),
        )

    async def find_by_source_id(self, source_id: str) -> Task | None:
        row = await self._db.fetch_one(
            "SELECT * FROM tasks WHERE source_id = ?", (source_id,)
        )
        if row is None:
            return None
        return Task.from_row(row)

    async def mark_failed(self, task_id: str, error: str):
        now = datetime.now(timezone.utc).isoformat()
        task = await self.get(task_id)
        if task is None:
            return
        handler_data = task.handler_data
        handler_data["error"] = error
        await self._db.execute(
            "UPDATE tasks SET status = ?, handler_data = ?, updated_at = ? WHERE id = ?",
            (TaskStatus.FAILED.value, json.dumps(handler_data), now, task_id),
        )

    # --- Chat messages ---

    async def save_chat_message(
        self, role: str, content: str, task_id: str | None = None
    ) -> str:
        import ulid as _ulid

        msg_id = str(_ulid.new())
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT INTO chat_messages (id, role, content, task_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (msg_id, role, content, task_id, now),
        )
        return msg_id

    async def list_chat_messages(self, limit: int = 200) -> list[dict]:
        return await self._db.fetch_all(
            "SELECT * FROM chat_messages ORDER BY created_at ASC LIMIT ?",
            (limit,),
        )

    async def clear_chat_messages(self):
        await self._db.execute("DELETE FROM chat_messages")

    # --- Schedules ---

    async def save_schedule(
        self,
        name: str,
        cron_expr: str,
        task_type: str,
        task_template: dict | None = None,
    ) -> str:
        import ulid as _ulid

        schedule_id = str(_ulid.new())
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT INTO schedules (id, name, cron_expr, task_type, task_template, enabled, next_run) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                schedule_id,
                name,
                cron_expr,
                task_type,
                json.dumps(task_template or {}),
                1,
                now,
            ),
        )
        return schedule_id

    async def list_schedules(self) -> list[dict]:
        return await self._db.fetch_all(
            "SELECT * FROM schedules ORDER BY name ASC"
        )

    async def get_schedule(self, schedule_id: str) -> dict | None:
        return await self._db.fetch_one(
            "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
        )

    async def delete_schedule(self, schedule_id: str):
        await self._db.execute(
            "DELETE FROM schedules WHERE id = ?", (schedule_id,)
        )

    async def update_schedule_enabled(self, schedule_id: str, enabled: bool):
        await self._db.execute(
            "UPDATE schedules SET enabled = ? WHERE id = ?",
            (1 if enabled else 0, schedule_id),
        )
