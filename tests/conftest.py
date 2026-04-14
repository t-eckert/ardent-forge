import pytest

from forge.agents import AgentContext
from forge.db import Database


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
def agent_ctx():
    """Minimal AgentContext for unit tests that exercise an agent directly."""
    return AgentContext(tools=[], store=None, settings=None)
