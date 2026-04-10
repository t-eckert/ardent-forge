from typing import Protocol

from forge.models import Task


class TaskHandler(Protocol):
    task_type: str

    async def triage(self, task: Task) -> bool: ...
    async def execute(self, task: Task) -> dict: ...
    async def verify(self, task: Task) -> bool: ...
    async def deliver(self, task: Task) -> dict: ...


class HandlerRegistry:
    def __init__(self):
        self._handlers: dict[str, TaskHandler] = {}

    def register(self, handler: TaskHandler):
        self._handlers[handler.task_type] = handler

    def get(self, task_type: str) -> TaskHandler | None:
        return self._handlers.get(task_type)
