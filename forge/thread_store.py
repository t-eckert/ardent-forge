"""ThreadStore — persistence for threads, thread_messages, and thread_tasks.

Kept separate from TaskStore even though both sit on the same Database —
the surface is distinct enough that sharing a single class would blur
responsibilities. `TaskStore` still owns everything about tasks; this
module owns conversations and the join table that links them.

See docs/superpowers/specs/2026-04-13-forge-orchestrator.md § Task ↔ Thread.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from forge.db import Database

Relation = str  # 'origin' | 'referenced'
Variant = str  # 'text' | 'widget' | 'task-dispatched' | 'task-resolved' | 'memory-saved'


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


@dataclass
class Thread:
    id: str
    title: str
    kind: str
    last_activity_at: str
    unread: bool
    created_at: str


@dataclass
class ThreadMessage:
    id: str
    thread_id: str
    role: str
    content: str
    variant: Variant
    widgets: list[dict[str, Any]]
    task_id: str | None
    created_at: str
    tool_use_id: str | None = None


@dataclass
class ThreadStore:
    _db: Database

    # ─── Threads ───────────────────────────────────────────────────────────

    async def create(
        self,
        *,
        title: str,
        kind: str = "chat",
        thread_id: str | None = None,
    ) -> Thread:
        t = Thread(
            id=thread_id or _gen_id("thread"),
            title=title,
            kind=kind,
            last_activity_at=_now(),
            unread=False,
            created_at=_now(),
        )
        await self._db.execute(
            "INSERT INTO threads (id, title, kind, last_activity_at, unread, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (t.id, t.title, t.kind, t.last_activity_at, int(t.unread), t.created_at),
        )
        return t

    async def get(self, thread_id: str) -> Thread | None:
        row = await self._db.fetch_one(
            "SELECT * FROM threads WHERE id = ?", (thread_id,)
        )
        return None if row is None else _thread_from_row(row)

    async def list(self, limit: int = 100) -> list[Thread]:
        rows = await self._db.fetch_all(
            "SELECT * FROM threads ORDER BY last_activity_at DESC LIMIT ?",
            (limit,),
        )
        return [_thread_from_row(r) for r in rows]

    async def mark_activity(self, thread_id: str, *, unread: bool = True) -> None:
        await self._db.execute(
            "UPDATE threads SET last_activity_at = ?, unread = ? WHERE id = ?",
            (_now(), int(unread), thread_id),
        )

    # ─── Messages ──────────────────────────────────────────────────────────

    async def append_message(
        self,
        *,
        thread_id: str,
        role: str,
        content: str,
        variant: Variant = "text",
        widgets: list[dict[str, Any]] | None = None,
        task_id: str | None = None,
        tool_use_id: str | None = None,
    ) -> ThreadMessage:
        msg = ThreadMessage(
            id=_gen_id("msg"),
            thread_id=thread_id,
            role=role,
            content=content,
            variant=variant,
            widgets=widgets or [],
            task_id=task_id,
            created_at=_now(),
            tool_use_id=tool_use_id,
        )
        await self._db.execute(
            "INSERT INTO thread_messages "
            "(id, thread_id, role, content, variant, widgets, task_id, tool_use_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                msg.id,
                msg.thread_id,
                msg.role,
                msg.content,
                msg.variant,
                json.dumps(msg.widgets),
                msg.task_id,
                msg.tool_use_id,
                msg.created_at,
            ),
        )
        # Resolution posts are by Forge; the user doesn't need an unread pip on
        # a message Forge wrote in response to their own request. Caller decides.
        return msg

    async def list_messages(self, thread_id: str, limit: int = 500) -> list[ThreadMessage]:
        rows = await self._db.fetch_all(
            "SELECT * FROM thread_messages WHERE thread_id = ? "
            "ORDER BY created_at ASC LIMIT ?",
            (thread_id, limit),
        )
        return [_message_from_row(r) for r in rows]

    # ─── Task ↔ Thread join ────────────────────────────────────────────────

    async def link_task(
        self,
        *,
        thread_id: str,
        task_id: str,
        relation: Relation = "origin",
    ) -> None:
        """Link a task to a thread. At most one 'origin' row per task is
        allowed by convention; enforce it by unlinking any existing origin first."""
        if relation not in ("origin", "referenced"):
            raise ValueError(f"Unknown relation: {relation!r}")
        if relation == "origin":
            await self._db.execute(
                "DELETE FROM thread_tasks WHERE task_id = ? AND relation = 'origin'",
                (task_id,),
            )
        await self._db.execute(
            "INSERT OR IGNORE INTO thread_tasks (thread_id, task_id, relation, created_at) "
            "VALUES (?, ?, ?, ?)",
            (thread_id, task_id, relation, _now()),
        )

    async def tasks_for_thread(self, thread_id: str) -> list[dict]:
        rows = await self._db.fetch_all(
            "SELECT task_id, relation, created_at FROM thread_tasks "
            "WHERE thread_id = ? ORDER BY created_at ASC",
            (thread_id,),
        )
        return [dict(r) for r in rows]

    async def origin_thread_for(self, task_id: str) -> str | None:
        row = await self._db.fetch_one(
            "SELECT thread_id FROM thread_tasks "
            "WHERE task_id = ? AND relation = 'origin' LIMIT 1",
            (task_id,),
        )
        return None if row is None else row["thread_id"]

    async def referencing_threads(self, task_id: str) -> list[str]:
        rows = await self._db.fetch_all(
            "SELECT thread_id FROM thread_tasks "
            "WHERE task_id = ? AND relation = 'referenced'",
            (task_id,),
        )
        return [r["thread_id"] for r in rows]


def _thread_from_row(row: dict) -> Thread:
    return Thread(
        id=row["id"],
        title=row["title"],
        kind=row["kind"],
        last_activity_at=row["last_activity_at"],
        unread=bool(row["unread"]),
        created_at=row["created_at"],
    )


def _message_from_row(row: dict) -> ThreadMessage:
    # tool_use_id was added after the initial schema — use .get-style access
    # via dict() conversion since aiosqlite.Row doesn't support .get().
    row_keys = row.keys() if hasattr(row, "keys") else []
    tool_use_id = row["tool_use_id"] if "tool_use_id" in row_keys else None
    return ThreadMessage(
        id=row["id"],
        thread_id=row["thread_id"],
        role=row["role"],
        content=row["content"],
        variant=row["variant"],
        widgets=json.loads(row["widgets"] or "[]"),
        task_id=row["task_id"],
        created_at=row["created_at"],
        tool_use_id=tool_use_id,
    )


__all__ = ["ThreadStore", "Thread", "ThreadMessage", "Relation", "Variant"]
