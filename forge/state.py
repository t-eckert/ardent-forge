from forge.models import TaskStatus

# Stage-aware transitions. Agents declare which stages they run; the coordinator
# skips stages not declared and transitions directly through. Every forward
# transition is legal here as long as it respects pipeline ordering.
VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.QUEUED: {TaskStatus.TRIAGING, TaskStatus.EXECUTING, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.TRIAGING: {TaskStatus.EXECUTING, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.EXECUTING: {TaskStatus.VERIFYING, TaskStatus.DELIVERING, TaskStatus.COMPLETED, TaskStatus.AWAITING_APPROVAL, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.VERIFYING: {TaskStatus.DELIVERING, TaskStatus.COMPLETED, TaskStatus.AWAITING_APPROVAL, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.DELIVERING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.AWAITING_APPROVAL: {TaskStatus.DELIVERING, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: {TaskStatus.QUEUED},
    TaskStatus.CANCELLED: set(),
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
