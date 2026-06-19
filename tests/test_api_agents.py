import pytest
from httpx import ASGITransport, AsyncClient

from forge.db import Database
from forge.main import create_app
from forge.agents import AgentRegistry
from forge.agents.echo import EchoAgent


@pytest.fixture
async def client():
    db = Database(":memory:")
    await db.initialize()
    app = create_app(db=db)
    registry = AgentRegistry()
    registry.register(EchoAgent())
    app.state.agent_registry = registry
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await db.close()


async def test_list_agents_reads_from_agent_registry(client):
    resp = await client.get("/api/agents")
    assert resp.status_code == 200
    names = [a["task_type"] for a in resp.json()]
    assert "echo" in names


async def test_get_agent_by_type(client):
    resp = await client.get("/api/agents/echo")
    assert resp.status_code == 200
    assert resp.json()["task_type"] == "echo"
