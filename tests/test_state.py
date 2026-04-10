import pytest

from forge.models import TaskStatus
from forge.state import InvalidTransition, transition


def test_valid_transitions():
    assert transition(TaskStatus.QUEUED, TaskStatus.TRIAGING) == TaskStatus.TRIAGING
    assert transition(TaskStatus.TRIAGING, TaskStatus.EXECUTING) == TaskStatus.EXECUTING
    assert transition(TaskStatus.EXECUTING, TaskStatus.VERIFYING) == TaskStatus.VERIFYING
    assert transition(TaskStatus.VERIFYING, TaskStatus.DELIVERING) == TaskStatus.DELIVERING
    assert transition(TaskStatus.DELIVERING, TaskStatus.COMPLETED) == TaskStatus.COMPLETED


def test_any_active_state_can_fail():
    for status in [TaskStatus.TRIAGING, TaskStatus.EXECUTING, TaskStatus.VERIFYING, TaskStatus.DELIVERING]:
        assert transition(status, TaskStatus.FAILED) == TaskStatus.FAILED


def test_queued_can_skip_to_executing():
    assert transition(TaskStatus.QUEUED, TaskStatus.EXECUTING) == TaskStatus.EXECUTING


def test_failed_can_retry_to_queued():
    assert transition(TaskStatus.FAILED, TaskStatus.QUEUED) == TaskStatus.QUEUED


def test_invalid_transition_raises():
    with pytest.raises(InvalidTransition):
        transition(TaskStatus.COMPLETED, TaskStatus.EXECUTING)


def test_completed_is_terminal():
    with pytest.raises(InvalidTransition):
        transition(TaskStatus.COMPLETED, TaskStatus.QUEUED)


def test_queued_cannot_complete_directly():
    with pytest.raises(InvalidTransition):
        transition(TaskStatus.QUEUED, TaskStatus.COMPLETED)
