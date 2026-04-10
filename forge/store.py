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
