from forge.models import TaskStatus

VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.QUEUED: {TaskStatus.TRIAGING, TaskStatus.EXECUTING},
    TaskStatus.TRIAGING: {TaskStatus.EXECUTING, TaskStatus.FAILED},
    TaskStatus.EXECUTING: {TaskStatus.VERIFYING, TaskStatus.FAILED},
    TaskStatus.VERIFYING: {TaskStatus.DELIVERING, TaskStatus.FAILED},
    TaskStatus.DELIVERING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: {TaskStatus.QUEUED},
}


class InvalidTransition(Exception):
    def __init__(self, from_status: TaskStatus, to_status: TaskStatus):
        super().__init__(f"Cannot transition from {from_status} to {to_status}")
        self.from_status = from_status
        self.to_status = to_status


def transition(current: TaskStatus, target: TaskStatus) -> TaskStatus:
    if target not in VALID_TRANSITIONS[current]:
        raise InvalidTransition(current, target)
    return target
