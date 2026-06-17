from forge.models import Task, TaskStatus, TaskType, TaskSource


def test_create_task():
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Fix the bug",
        description="There is a bug in main.py",
    )
    assert task.status == TaskStatus.QUEUED
    assert task.type == TaskType.CODE
    assert task.source == TaskSource.CHAT
    assert task.retries == 0
    assert task.id is not None
    assert len(task.id) > 0


def test_create_task_with_repo():
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.LINEAR,
        title="Add feature",
        description="New feature",
        repo="t-eckert/ardent-forge",
        source_id="LIN-123",
    )
    assert task.repo == "t-eckert/ardent-forge"
    assert task.source_id == "LIN-123"


def test_task_to_row_and_back():
    task = Task.new(
        task_type=TaskType.CODE,
        source=TaskSource.CHAT,
        title="Roundtrip",
        description="Test serialization",
    )
    row = task.to_row()
    restored = Task.from_row(row)
    assert restored.id == task.id
    assert restored.title == task.title
    assert restored.status == task.status
    assert restored.handler_data == task.handler_data


def test_task_type_includes_plan_and_tickets():
    from forge.models import TaskType
    assert TaskType.PLAN == "plan"
    assert TaskType.TICKETS == "tickets"


def test_task_resilience_fields_default_and_roundtrip():
    from datetime import datetime, timezone
    from forge.models import Task, TaskSource, TaskType

    task = Task.new(
        task_type=TaskType.ECHO,
        source=TaskSource.CHAT,
        title="t",
        description="d",
    )
    # Defaults
    assert task.max_retries == 3
    assert task.available_at is None
    assert task.failure_kind is None

    # Round-trip through to_row/from_row with non-default values
    task = task.model_copy(update={
        "max_retries": 5,
        "available_at": datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc),
        "failure_kind": "timeout",
    })
    restored = Task.from_row(task.to_row())
    assert restored.max_retries == 5
    assert restored.available_at == task.available_at
    assert restored.failure_kind == "timeout"
