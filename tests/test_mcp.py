import pytest

from forge.db import Database
from forge.mcp import server as mcp_server
from forge.memory import MemoryStore
from forge.models import TaskStatus
from forge.repos.models import Repo
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


async def test_write_memory_rejects_path_traversal(memory):
    mcp_server.configure(memory=memory)
    out = await mcp_server.write_memory(
        name="x", description="y", type="user", body="z",
        filename="../../etc/passwd",
    )
    assert "error" in out


class _FakeRegistry:
    def __init__(self, repos):
        self._repos = repos

    def list(self):
        return self._repos

    def get(self, name):
        return next((r for r in self._repos if r.name == name), None)


def _repo(name):
    return Repo(name=name, path=f"/repos/{name}", default_branch="main")


async def test_list_and_get_repos():
    reg = _FakeRegistry([_repo("alpha"), _repo("beta")])
    mcp_server.configure(repo_registry=reg)

    repos = await mcp_server.list_repos()
    assert {r["name"] for r in repos} == {"alpha", "beta"}

    one = await mcp_server.get_repo("alpha")
    assert one["name"] == "alpha"

    missing = await mcp_server.get_repo("zeta")
    assert missing == {"error": "Repo not found: zeta"}


async def test_schedule_create_list_delete(store):
    mcp_server.configure(store=store)

    created = await mcp_server.create_schedule(
        name="Nightly",
        cron_expr="0 2 * * *",
        task_type="code",
        repo="t-eckert/ardent-forge",
        prompt_template="Run the nightly maintenance pass",
        label="maint",
    )
    sid = created["id"]
    assert created["name"] == "Nightly"

    listed = await mcp_server.list_schedules()
    assert any(s["id"] == sid for s in listed)

    deleted = await mcp_server.delete_schedule(sid)
    assert deleted == {"deleted": sid}

    assert await mcp_server.delete_schedule(sid) == {"error": "Schedule not found"}


class _FakeHit:
    def __init__(self, path, line_number, line):
        self.path = path
        self.line_number = line_number
        self.line = line


class _FakeReader:
    def search(self, query, path_prefix=None):
        return [_FakeHit("notes/a.md", 3, f"match for {query}")]

    def read(self, path):
        if path == "notes/a.md":
            return "file body"
        raise FileNotFoundError(path)


async def test_search_notebook_and_read_note():
    mcp_server.configure(notebook_reader=_FakeReader())

    hits = await mcp_server.search_notebook("foo")
    assert hits == [{"path": "notes/a.md", "line_number": 3, "line": "match for foo"}]

    note = await mcp_server.read_note("notes/a.md")
    assert note == {"path": "notes/a.md", "content": "file body"}

    missing = await mcp_server.read_note("notes/missing.md")
    assert "error" in missing


class _FakeTool:
    async def execute(self, **kwargs):
        return {"query": kwargs.get("query"), "results": []}


class _FakeConnectors:
    def __init__(self, tool):
        self._tool = tool

    def find_tool(self, name):
        return self._tool if name == "web_search" else None


async def test_web_search_uses_connector_tool():
    mcp_server.configure(connectors=_FakeConnectors(_FakeTool()))
    out = await mcp_server.web_search("latest python release")
    assert out["query"] == "latest python release"


async def test_web_search_missing_connector():
    mcp_server.configure(connectors=_FakeConnectors(None))
    out = await mcp_server.web_search("anything")
    assert out == {"error": "web search not configured"}
