from pydantic import BaseModel


class Repo(BaseModel):
    name: str
    path: str
    default_branch: str


class Project(BaseModel):
    name: str
    path: str
    repos: list[Repo]
