from pydantic import BaseModel


class RepoConfig(BaseModel):
    dev_port: int | None = None
    claude_label: str | None = None
    allowed_op_paths: list[str] = []
    cron_tasks: list[dict] = []


class Repo(BaseModel):
    name: str
    path: str
    default_branch: str
    dev_port: int | None = None
