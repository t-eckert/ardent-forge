import logging
import re
from pathlib import Path

from forge.claude import ClaudeRunner
from forge.git import GitOps
from forge.models import Task

logger = logging.getLogger(__name__)

SPEC_PATH_RE = re.compile(r"(docs/superpowers/specs/[\w\-.]+\.md)")


def extract_spec_path(description: str) -> str | None:
    match = SPEC_PATH_RE.search(description or "")
    return match.group(1) if match else None


def build_plan_prompt(spec_path: str, spec_body: str) -> str:
    return f"""You are the Ardent Forge planner. Read the spec below and produce an implementation plan.

Write the plan to `docs/superpowers/plans/` using the same filename date-prefix as the spec.
Format: numbered top-level tasks, each with bite-sized steps, exact file paths, complete code blocks, explicit test-first TDD cadence, and a commit step. Match the style of existing plans in docs/superpowers/plans/.

After writing the plan file, also update the spec file's frontmatter `status` field from `ready-to-plan` to `planned`.

Do NOT modify any other files. Your write scope is limited to the plan file and the spec's frontmatter.

Spec path: {spec_path}

Spec content:
---
{spec_body}
---
"""


class PlanHandler:
    task_type: str = "plan"

    def __init__(
        self,
        workspace_dir: str = "/var/lib/ardent-forge/repos",
        specs_dir: str = "docs/superpowers/specs",
        self_repo: str = "t-eckert/ardent-forge",
        claude_model: str = "claude-opus-4-20250514",
        claude_timeout: int = 600,
    ):
        self._git = GitOps(workspace_dir)
        self._claude = ClaudeRunner(model=claude_model, timeout=claude_timeout)
        self._specs_dir = specs_dir
        self._self_repo = self_repo

    async def triage(self, task: Task) -> bool:
        spec_path = extract_spec_path(task.description)
        if not spec_path:
            logger.warning(f"Task {task.id} has no spec path in description")
            return False
        return True

    async def execute(self, task: Task) -> dict:
        raise NotImplementedError  # Task 6

    async def verify(self, task: Task) -> bool:
        raise NotImplementedError  # Task 7

    async def deliver(self, task: Task) -> dict:
        raise NotImplementedError  # Task 8
