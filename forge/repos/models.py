from pydantic import BaseModel


class Repo(BaseModel):
    name: str
    path: str
    default_branch: str
