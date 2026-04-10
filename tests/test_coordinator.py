import asyncio

import pytest

from forge.coordinator import Coordinator
from forge.db import Database
from forge.handlers import HandlerRegistry
from forge.handlers.echo import EchoHandler
from forge.models import Task, TaskSource, TaskStatus, TaskType
from forge.store import TaskStore


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
def store(db):
    return TaskStore(db)


@pytest.fixture
def registry():
    reg = HandlerRegistry()
    reg.register(EchoHandler())
    return reg


@pytest.fixture
def coordinator(store, registry):
    return Coordinator(store=store, registry=registry, max_concurrent=2)


async def test_process_single_task(coordinator, store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Process me",
        description="Test processing",
    )
    # Echo handler is registered for "echo" type, not "code"
    # So let's make an echo-typed task
    task.type = TaskType.CODE  # Will not find handler
    await store.save(task)

    # No handler for "code" yet — task should fail
    await coordinator.process_pending()
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.FAILED


async def test_process_echo_task(coordinator, store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Echo me",
        description="Test echo",
    )
    # Override type to match echo handler
    task = task.model_copy(update={"type": "echo"})
    await store.save(task)

    await coordinator.process_pending()
    loaded = await store.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.COMPLETED
    assert loaded.result is not None


async def test_respects_max_concurrent(coordinator, store):
    tasks = []
    for i in range(5):
        task = Task.new(
            task_type=TaskType.CODE,
            source=TaskSource.CHAT,
            title=f"Task {i}",
            description=f"Concurrent {i}",
        )
        task = task.model_copy(update={"type": "echo"})
        await store.save(task)
        tasks.append(task)

    await coordinator.process_pending()

    completed = await store.list_by_status(TaskStatus.COMPLETED)
    # Should process up to max_concurrent (2) per cycle
    assert len(completed) == 2


async def test_coordinator_tick_processes_and_returns(coordinator, store):
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Tick test",
        description="Test tick",
    )
    task = task.model_copy(update={"type": "echo"})
    await store.save(task)

    processed = await coordinator.tick()
    assert processed == 1
