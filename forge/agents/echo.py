from forge.agents import AgentContext
from forge.models import Task


class EchoAgent:
    name = "echo"
    task_type = "echo"
    stages = ["execute"]
    connectors: list[str] = []

    async def execute(self, task: Task, ctx: AgentContext) -> dict:
        return {"message": f"Echo: {task.title}"}
