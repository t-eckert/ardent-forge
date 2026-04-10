import pytest

from forge.handlers import HandlerRegistry
from forge.handlers.echo import EchoHandler
from forge.models import Task, TaskSource, TaskType


@pytest.fixture
def task():
    return Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Echo test",
        description="Test the echo handler",
    )


@pytest.fixture
def registry():
    reg = HandlerRegistry()
    reg.register(EchoHandler())
    return reg


async def test_echo_handler_triage(task):
    handler = EchoHandler()
    result = await handler.triage(task)
    assert result is True


async def test_echo_handler_execute(task):
    handler = EchoHandler()
    result = await handler.execute(task)
    assert "echo" in result["message"].lower()


async def test_echo_handler_verify(task):
    handler = EchoHandler()
    result = await handler.verify(task)
    assert result is True


async def test_echo_handler_deliver(task):
    handler = EchoHandler()
    result = await handler.deliver(task)
    assert "delivered" in result["status"]


async def test_registry_finds_handler(registry, task):
    handler = registry.get("echo")
    assert handler is not None
    assert handler.task_type == "echo"


async def test_registry_returns_none_for_unknown(registry):
    handler = registry.get("nonexistent")
    assert handler is None
