"""Tests for ThreadStore: threads, messages, task↔thread join semantics."""

import pytest

from forge.db import Database
from forge.thread_store import ThreadStore


@pytest.fixture
async def thread_store(db: Database):
    return ThreadStore(db)


# ─── Threads ────────────────────────────────────────────────────────────────


async def test_create_and_get(thread_store: ThreadStore):
    t = await thread_store.create(title="Morning briefing", kind="code+tools")
    assert t.id.startswith("thread-")
    assert t.title == "Morning briefing"
    assert t.kind == "code+tools"
    got = await thread_store.get(t.id)
    assert got is not None
    assert got.id == t.id


async def test_list_orders_by_activity(thread_store: ThreadStore):
    first = await thread_store.create(title="Old")
    second = await thread_store.create(title="New")
    # mark_activity bumps last_activity_at
    await thread_store.mark_activity(first.id)
    threads = await thread_store.list()
    assert [t.id for t in threads[:2]] == [first.id, second.id]


async def test_mark_activity_flips_unread(thread_store: ThreadStore):
    t = await thread_store.create(title="x")
    await thread_store.mark_activity(t.id, unread=True)
    got = await thread_store.get(t.id)
    assert got.unread is True


# ─── Messages ───────────────────────────────────────────────────────────────


async def test_append_and_list_messages(thread_store: ThreadStore):
    t = await thread_store.create(title="x")
    await thread_store.append_message(thread_id=t.id, role="user", content="hello")
    await thread_store.append_message(
        thread_id=t.id,
        role="assistant",
        content="hi",
        variant="text",
    )
    msgs = await thread_store.list_messages(t.id)
    assert len(msgs) == 2
    assert [m.role for m in msgs] == ["user", "assistant"]


async def test_message_widgets_round_trip(thread_store: ThreadStore):
    t = await thread_store.create(title="x")
    payload = {"tool": "weather.forecast", "currentC": 18}
    m = await thread_store.append_message(
        thread_id=t.id,
        role="assistant",
        content="...",
        variant="widget",
        widgets=[payload],
    )
    assert m.widgets == [payload]
    [loaded] = await thread_store.list_messages(t.id)
    assert loaded.widgets == [payload]


# ─── Task ↔ Thread join ─────────────────────────────────────────────────────


async def test_link_task_origin(thread_store: ThreadStore, db: Database):
    # Insert a stub task row so the FK is satisfied.
    await db.execute(
        "INSERT INTO tasks (id, type, status, source, title, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("task-1", "code", "queued", "chat", "t", "d", "now", "now"),
    )
    t = await thread_store.create(title="x")
    await thread_store.link_task(thread_id=t.id, task_id="task-1", relation="origin")

    assert await thread_store.origin_thread_for("task-1") == t.id
    rows = await thread_store.tasks_for_thread(t.id)
    assert rows[0]["task_id"] == "task-1"
    assert rows[0]["relation"] == "origin"


async def test_origin_is_unique_per_task(thread_store: ThreadStore, db: Database):
    await db.execute(
        "INSERT INTO tasks (id, type, status, source, title, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("task-1", "code", "queued", "chat", "t", "d", "now", "now"),
    )
    first = await thread_store.create(title="first")
    second = await thread_store.create(title="second")
    await thread_store.link_task(thread_id=first.id, task_id="task-1", relation="origin")
    await thread_store.link_task(thread_id=second.id, task_id="task-1", relation="origin")

    # Only the newer origin remains.
    assert await thread_store.origin_thread_for("task-1") == second.id


async def test_referenced_accumulates(thread_store: ThreadStore, db: Database):
    await db.execute(
        "INSERT INTO tasks (id, type, status, source, title, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("task-1", "code", "queued", "chat", "t", "d", "now", "now"),
    )
    a = await thread_store.create(title="a")
    b = await thread_store.create(title="b")
    await thread_store.link_task(thread_id=a.id, task_id="task-1", relation="referenced")
    await thread_store.link_task(thread_id=b.id, task_id="task-1", relation="referenced")

    assert set(await thread_store.referencing_threads("task-1")) == {a.id, b.id}
    assert await thread_store.origin_thread_for("task-1") is None


async def test_unknown_relation_rejected(thread_store: ThreadStore):
    t = await thread_store.create(title="x")
    with pytest.raises(ValueError):
        await thread_store.link_task(thread_id=t.id, task_id="task-1", relation="bogus")
