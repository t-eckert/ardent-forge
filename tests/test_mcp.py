import pytest

from forge.db import Database
from forge.mcp import server as mcp_server
from forge.memory import MemoryStore
from forge.models import TaskStatus
from forge.store import TaskStore


class _NudgeSpy:
    def __init__(self):
        self.calls = 0

    def nudge(self):
        self.calls += 1


@pytest.fixture
async def store():
    db = Database(":memory:")
    await db.initialize()
    yield TaskStore(db)
    await db.close()


@pytest.fixture(autouse=True)
def _reset_mcp_globals():
    # Each test configures its own services; clear between tests.
    mcp_server._store = None
    mcp_server._memory = None
    mcp_server._repo_registry = None
    mcp_server._coordinator = None
    mcp_server._connectors = None
    mcp_server._notebook_reader = None
    yield


async def test_dispatch_task_saves_and_nudges(store):
    spy = _NudgeSpy()
    mcp_server.configure(store=store, coordinator=spy)

    out = await mcp_server.dispatch_task(
        type="echo", title="Hello", description="Do the thing"
    )

    assert "id" in out
    assert out["status"] == TaskStatus.QUEUED.value
    assert spy.calls == 1
    saved = await store.get(out["id"])
    assert saved is not None
    assert saved.title == "Hello"


async def test_dispatch_task_rejects_oversize_title(store):
    mcp_server.configure(store=store)
    out = await mcp_server.dispatch_task(
        type="echo", title="x" * 501, description="d"
    )
    assert "error" in out


async def test_get_task_round_trip(store):
    mcp_server.configure(store=store)
    created = await mcp_server.dispatch_task(
        type="echo", title="T", description="D"
    )
    got = await mcp_server.get_task(created["id"])
    assert got["id"] == created["id"]
    assert got["title"] == "T"


async def test_get_task_not_found(store):
    mcp_server.configure(store=store)
    assert await mcp_server.get_task("nope") == {"error": "Task not found"}


async def test_list_tasks_filters_by_status(store):
    mcp_server.configure(store=store)
    await mcp_server.dispatch_task(type="echo", title="A", description="D")
    all_tasks = await mcp_server.list_tasks()
    assert len(all_tasks) == 1
    queued = await mcp_server.list_tasks(status="queued")
    assert len(queued) == 1
    done = await mcp_server.list_tasks(status="completed")
    assert done == []


async def test_list_tasks_invalid_status(store):
    mcp_server.configure(store=store)
    out = await mcp_server.list_tasks(status="bogus")
    assert isinstance(out, dict) and "error" in out


async def test_list_tasks_filters_by_type(store):
    mcp_server.configure(store=store)
    await mcp_server.dispatch_task(type="echo", title="E", description="D")
    await mcp_server.dispatch_task(type="code", title="C", description="D")
    echoes = await mcp_server.list_tasks(type="echo")
    assert len(echoes) == 1
    assert echoes[0]["type"] == "echo"


async def test_dispatch_task_rejects_oversize_description(store):
    mcp_server.configure(store=store)
    out = await mcp_server.dispatch_task(
        type="echo", title="t", description="x" * 50_001
    )
    assert "error" in out


async def test_dispatch_task_rejects_oversize_type(store):
    mcp_server.configure(store=store)
    out = await mcp_server.dispatch_task(
        type="x" * 65, title="t", description="d"
    )
    assert "error" in out


@pytest.fixture
def memory(tmp_path):
    return MemoryStore(tmp_path)


async def test_memory_write_read_list_delete(memory):
    mcp_server.configure(memory=memory)

    written = await mcp_server.write_memory(
        name="Likes tabs",
        description="prefers tabs",
        type="user",
        body="The user prefers tabs over spaces.",
    )
    assert written["name"] == "Likes tabs"
    fname = written["filename"]

    listed = await mcp_server.list_memory()
    assert any(e["filename"] == fname for e in listed)

    read = await mcp_server.read_memory(fname)
    assert read["body"] == "The user prefers tabs over spaces.\n"

    deleted = await mcp_server.delete_memory(fname)
    assert deleted == {"deleted": fname}
    assert (await mcp_server.read_memory(fname)) == {
        "error": f"No memory: {fname}"
    }


async def test_memory_write_rejects_bad_type(memory):
    mcp_server.configure(memory=memory)
    out = await mcp_server.write_memory(
        name="x", description="y", type="bogus", body="z"
    )
    assert "error" in out
