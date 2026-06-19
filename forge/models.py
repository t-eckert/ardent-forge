import json
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field
import ulid


class TaskStatus(StrEnum):
    QUEUED = "queued"
    TRIAGING = "triaging"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    DELIVERING = "delivering"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"
    CANCELLED = "cancelled"


class TaskType(StrEnum):
    CODE = "code"
    PLAN = "plan"
    TICKETS = "tickets"
    ECHO = "echo"


class TaskSource(StrEnum):
    LINEAR = "linear"
    CHAT = "chat"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    MANUAL = "manual"


class Task(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    id: str
    type: TaskType | str
    status: TaskStatus
    source: TaskSource
    source_id: str | None = None
    repo: str | None = None
    title: str
    description: str
    handler_data: dict = Field(default_factory=dict)
    result: dict | None = None
    retries: int = 0
    max_retries: int = 3
    available_at: datetime | None = None
    failure_kind: str | None = None
    require_approval: bool = False
    continues_task_id: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def new(
        cls,
        task_type: TaskType,
        source: TaskSource,
        title: str,
        description: str,
        repo: str | None = None,
        source_id: str | None = None,
        require_approval: bool = False,
        continues_task_id: str | None = None,
    ) -> "Task":
        now = datetime.now(timezone.utc)
        return cls(
            id=str(ulid.new()),
            type=task_type,
            status=TaskStatus.QUEUED,
            source=source,
            source_id=source_id,
            repo=repo,
            title=title,
            description=description,
            require_approval=require_approval,
            continues_task_id=continues_task_id,
            created_at=now,
            updated_at=now,
        )

    def to_row(self) -> dict:
        return {
            "id": self.id,
            "type": str(self.type),
            "status": self.status.value,
            "source": self.source.value,
            "source_id": self.source_id,
            "repo": self.repo,
            "title": self.title,
            "description": self.description,
            "handler_data": json.dumps(self.handler_data),
            "result": json.dumps(self.result) if self.result else None,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "available_at": (
                self.available_at.isoformat() if self.available_at else None
            ),
            "failure_kind": self.failure_kind,
            "require_approval": int(self.require_approval),
            "continues_task_id": self.continues_task_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }

    @classmethod
    def from_row(cls, row: dict) -> "Task":
        try:
            task_type = TaskType(row["type"])
        except ValueError:
            task_type = row["type"]  # type: ignore[assignment]
        return cls(
            id=row["id"],
            type=task_type,
            status=TaskStatus(row["status"]),
            source=TaskSource(row["source"]),
            source_id=row.get("source_id"),
            repo=row.get("repo"),
            title=row["title"],
            description=row["description"],
            handler_data=json.loads(row["handler_data"]) if row["handler_data"] else {},
            result=json.loads(row["result"]) if row.get("result") else None,
            retries=row["retries"],
            max_retries=row.get("max_retries", 3),
            available_at=(
                datetime.fromisoformat(row["available_at"])
                if row.get("available_at")
                else None
            ),
            failure_kind=row.get("failure_kind"),
            require_approval=bool(row.get("require_approval", 0)),
            continues_task_id=row.get("continues_task_id"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row.get("completed_at")
                else None
            ),
        )
