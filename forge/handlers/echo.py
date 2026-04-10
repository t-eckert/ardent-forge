from forge.models import Task


class EchoHandler:
    task_type: str = "echo"

    async def triage(self, task: Task) -> bool:
        return True

    async def execute(self, task: Task) -> dict:
        return {"message": f"Echo: {task.title}"}

    async def verify(self, task: Task) -> bool:
        return True

    async def deliver(self, task: Task) -> dict:
        return {"status": "delivered", "title": task.title}
