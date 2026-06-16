import logging
import re
from pathlib import Path

from forge.agents import AgentContext, record_triage_reason
from forge.claude import ClaudeRunner
from forge.git import GitOps
from forge.guardrails import check_handler_allowlist
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


class PlanAgent:
    """No-triage pipeline: spec-derived → claude writes plan → verify allowlist → PR."""

    name = "plan"
    task_type = "plan"
    stages = ["triage", "execute", "verify", "deliver"]
    connectors = ["github"]

    def __init__(
        self,
        workspace_dir: str = "/var/lib/ardent-forge/repos",
        specs_dir: str = "docs/superpowers/specs",
        self_repo: str = "t-eckert/ardent-forge",
        claude_model: str = "opus",
        claude_timeout: int = 600,
    ):
        self._git = GitOps(workspace_dir)
        self._claude = ClaudeRunner(model=claude_model, timeout=claude_timeout)
        self._specs_dir = specs_dir
        self._self_repo = self_repo

    async def triage(self, task: Task, ctx: AgentContext) -> bool:
        spec_path = extract_spec_path(task.description)
        if not spec_path:
            logger.warning(f"Task {task.id} has no spec path in description")
            await record_triage_reason(
                ctx,
                task,
                "No spec path found in the task description. A plan task needs a "
                "`spec:` reference to a design doc under docs/superpowers/specs/.",
            )
            return False
        return True

    async def execute(self, task: Task, ctx: AgentContext) -> dict:
        spec_path = extract_spec_path(task.description)
        if not spec_path:
            raise RuntimeError(f"No spec path in task {task.id}")

        repo_url = f"https://github.com/{self._self_repo}.git"
        branch_name = f"forge/plan-{task.id[:12]}"

        repo_path = await self._git.ensure_repo(repo_url, self._self_repo)
        worktree_path = await self._git.create_worktree(repo_path, branch_name)

        spec_abs = Path(worktree_path) / spec_path
        if not spec_abs.exists():
            raise RuntimeError(f"Spec file not found in worktree: {spec_abs}")
        spec_body = spec_abs.read_text()

        prompt = build_plan_prompt(spec_path=spec_path, spec_body=spec_body)
        output = await self._claude.run(prompt, worktree_path)

        return {
            "worktree_path": worktree_path,
            "repo_path": repo_path,
            "branch_name": branch_name,
            "spec_path": spec_path,
            "claude_output": output[:2000],
        }

    async def verify(self, task: Task, ctx: AgentContext) -> bool:
        worktree_path = task.handler_data.get("worktree_path")
        if not worktree_path:
            logger.error(f"No worktree_path in handler_data for task {task.id}")
            return False
        try:
            changed = await self._git.get_working_tree_changes(worktree_path)
        except RuntimeError as e:
            logger.error(f"Failed to list changed files: {e}")
            return False
        violation = check_handler_allowlist(
            handler=self.task_type,
            repo=self._self_repo,
            changed_files=changed,
        )
        if violation:
            logger.error(f"Verification failed for task {task.id}: {violation}")
            return False
        if not changed:
            logger.error(f"Plan agent produced no changes for task {task.id}")
            return False
        return True

    async def deliver(self, task: Task, ctx: AgentContext) -> dict:
        worktree_path = task.handler_data.get("worktree_path")
        repo_path = task.handler_data.get("repo_path")
        branch_name = task.handler_data.get("branch_name", "")
        spec_path = task.handler_data.get("spec_path")

        if not worktree_path or not repo_path or not spec_path:
            return {"status": "delivered", "error": "Missing handler_data"}

        commit_msg = f"plan: {task.title}"
        await self._git.commit_all(worktree_path, commit_msg)

        body = (
            f"Plan generated from {spec_path}.\n\n"
            "On merge, Ardent Forge will create Linear tickets for each numbered step.\n\n"
            "---\nAutomated by Ardent Forge (plan agent)"
        )
        try:
            pr_url = await self._git.create_pr(
                worktree_path=worktree_path,
                title=f"plan: {task.title}",
                body=body,
            )
        except RuntimeError as e:
            logger.error(f"PR creation failed: {e}")
            pr_url = f"PR creation failed: {e}"

        try:
            await self._git.cleanup_worktree(repo_path, worktree_path)
        except RuntimeError:
            logger.warning(f"Failed to cleanup worktree {worktree_path}")

        return {
            "status": "delivered",
            "pr_url": pr_url,
            "branch": branch_name,
            "spec_path": spec_path,
        }
