"""Phase 3 dispatcher tests — cron schedules, Linear dispatch, chat repo field."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta

from forge.db import Database
from forge.store import TaskStore
from forge.models import Task, TaskSource, TaskType


# ── Helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def store(tmp_path):
    db = Database(":memory:")
    await db.initialize()
    s = TaskStore(db)
    yield s
    await db.close()


# ── Cron schedule store ───────────────────────────────────────────────────────


async def test_save_schedule_sets_next_run_from_cron(store):
    sid = await store.save_schedule(
        name="nightly",
        cron_expr="0 2 * * *",
        task_type="code",
    )
    sched = await store.get_schedule(sid)
    assert sched is not None
    # next_run should be in the future, not "now"
    next_run = datetime.fromisoformat(sched["next_run"])
    assert next_run > datetime.now(timezone.utc)


async def test_list_due_schedules_returns_overdue(store):
    sid = await store.save_schedule(
        name="overdue",
        cron_expr="* * * * *",
        task_type="code",
        task_template={"repo": "owner/repo", "description": "do the thing"},
    )
    # Force next_run into the past
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    await store._db.execute("UPDATE schedules SET next_run = ? WHERE id = ?", (past, sid))
    await store._db._conn.commit()

    due = await store.list_due_schedules(datetime.now(timezone.utc).isoformat())
    assert len(due) == 1
    assert due[0]["id"] == sid


async def test_list_due_schedules_skips_future(store):
    await store.save_schedule(name="future", cron_expr="0 0 1 1 *", task_type="code")
    due = await store.list_due_schedules(datetime.now(timezone.utc).isoformat())
    assert due == []


async def test_list_due_schedules_skips_disabled(store):
    sid = await store.save_schedule(name="dis", cron_expr="* * * * *", task_type="code")
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    await store._db.execute(
        "UPDATE schedules SET next_run = ?, enabled = 0 WHERE id = ?", (past, sid)
    )
    await store._db._conn.commit()
    due = await store.list_due_schedules(datetime.now(timezone.utc).isoformat())
    assert due == []


async def test_update_schedule_after_run(store):
    sid = await store.save_schedule(name="x", cron_expr="* * * * *", task_type="code")
    last = datetime.now(timezone.utc).isoformat()
    nxt = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
    await store.update_schedule_after_run(sid, last, nxt)
    sched = await store.get_schedule(sid)
    assert sched["last_run"] == last
    assert sched["next_run"] == nxt


# ── Coordinator schedule firing ───────────────────────────────────────────────


async def test_coordinator_fires_due_schedule(store):
    from forge.coordinator import Coordinator
    from forge.agents import AgentRegistry

    sid = await store.save_schedule(
        name="daily-cleanup",
        cron_expr="0 2 * * *",
        task_type="code",
        task_template={"repo": "owner/app", "description": "cleanup unused deps"},
    )
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    await store._db.execute("UPDATE schedules SET next_run = ? WHERE id = ?", (past, sid))
    await store._db._conn.commit()

    coordinator = Coordinator(store=store, registry=AgentRegistry())
    fired = await coordinator._fire_due_schedules()

    assert fired == 1
    tasks = await store.list_all()
    assert len(tasks) == 1
    t = tasks[0]
    assert t.type == TaskType.CODE
    assert t.source == TaskSource.SCHEDULE
    assert t.repo == "owner/app"
    assert t.description == "cleanup unused deps"

    # next_run should be advanced past now
    sched = await store.get_schedule(sid)
    assert datetime.fromisoformat(sched["next_run"]) > datetime.now(timezone.utc)


async def test_coordinator_skips_unknown_task_type(store):
    from forge.coordinator import Coordinator
    from forge.agents import AgentRegistry

    sid = await store.save_schedule(name="bad", cron_expr="* * * * *", task_type="nonexistent")
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    await store._db.execute("UPDATE schedules SET next_run = ? WHERE id = ?", (past, sid))
    await store._db._conn.commit()

    coordinator = Coordinator(store=store, registry=AgentRegistry())
    fired = await coordinator._fire_due_schedules()
    assert fired == 0
    assert await store.list_all() == []


# ── Schedule API ──────────────────────────────────────────────────────────────


async def test_create_schedule_with_repo_and_prompt(store):
    from forge.api.schedules import _build_template, CreateScheduleRequest

    req = CreateScheduleRequest(
        name="nightly lint",
        cron_expr="0 2 * * *",
        task_type="code",
        repo="owner/my-app",
        prompt_template="Fix all linting errors",
        label="nightly",
    )
    template = _build_template(req)
    assert template["repo"] == "owner/my-app"
    assert template["description"] == "Fix all linting errors"
    assert template["label"] == "nightly"
    assert template["title"] == "Fix all linting errors"


# ── Linear poller dispatch ────────────────────────────────────────────────────


async def test_linear_poller_detects_claude_label(store):
    from forge.linear.poller import LinearPoller
    from forge.linear.client import LinearClient

    client = MagicMock(spec=LinearClient)
    client.get_labeled_issues = AsyncMock(
        return_value=[
            {
                "id": "issue-1",
                "identifier": "ENG-42",
                "title": "Fix the bug",
                "description": "Repo: owner/my-app\n\nThere is a bug.",
                "labels": {"nodes": [{"name": "ardent-forge"}, {"name": "claude"}]},
            }
        ]
    )

    poller = LinearPoller(client=client, store=store, team_id="team-1")
    created = await poller.poll()

    assert created == 1
    tasks = await store.list_all()
    assert tasks[0].type == TaskType.CODE
    assert tasks[0].repo == "owner/my-app"
    assert tasks[0].source == TaskSource.LINEAR


async def test_linear_poller_parses_repo_variants(store):
    from forge.linear.poller import LinearPoller

    poller = LinearPoller(client=MagicMock(), store=store, team_id="t")
    assert poller._parse_repo("Repo: owner/app") == "owner/app"
    assert poller._parse_repo("**Repo:** owner/app\n\nmore text") == "owner/app"
    assert poller._parse_repo("repo: owner/app") == "owner/app"
    assert poller._parse_repo("No repo here") is None


async def test_linear_poller_post_result_sends_comment(store):
    from forge.linear.poller import LinearPoller
    from forge.linear.client import LinearClient

    client = MagicMock(spec=LinearClient)
    client.add_comment = AsyncMock(return_value=True)

    poller = LinearPoller(client=client, store=store, team_id="t")
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.LINEAR,
        title="Fix bug",
        description="...",
        source_id="issue-99",
    )
    task = task.model_copy(update={"result": {"pr_url": "https://github.com/owner/repo/pull/1"}})
    await poller.post_result(task)

    client.add_comment.assert_awaited_once()
    args = client.add_comment.call_args
    assert "issue-99" in args[0]
    assert "https://github.com/owner/repo/pull/1" in args[0][1]


async def test_linear_poller_post_result_skips_non_linear(store):
    from forge.linear.poller import LinearPoller

    client = MagicMock()
    client.add_comment = AsyncMock()
    poller = LinearPoller(client=client, store=store, team_id="t")

    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="x",
        description="y",
    )
    await poller.post_result(task)
    client.add_comment.assert_not_called()


async def test_linear_poller_post_result_skips_failed_pr(store):
    from forge.linear.poller import LinearPoller

    client = MagicMock()
    client.add_comment = AsyncMock()
    poller = LinearPoller(client=client, store=store, team_id="t")

    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.LINEAR,
        title="x",
        description="y",
        source_id="issue-5",
    )
    task = task.model_copy(update={"result": {"pr_url": "PR creation failed: auth error"}})
    await poller.post_result(task)
    client.add_comment.assert_not_called()
