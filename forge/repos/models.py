from pydantic import BaseModel


class RepoConfig(BaseModel):
    dev_port: int | None = None
    claude_label: str | None = None
    # env vars injected at task start; values may be op:// refs resolved by OPConnector
    env: dict[str, str] = {}
    cron_tasks: list[dict] = []

    @property
    def allowed_op_paths(self) -> list[str]:
        """op:// references declared in env — the only refs OPConnector will resolve."""
        return [v for v in self.env.values() if v.startswith("op://")]


class Repo(BaseModel):
    name: str
    path: str
    default_branch: str
    dev_port: int | None = None
