import logging

from forge.agents import AgentContext
from forge.claude import build_prompt
from forge.git import GitOps
from forge.models import Task
from forge.verify import run_verification
from forge.zellij import ZellijRunner

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


class CodeAgent:
    """Full-pipeline agent: clones repo, runs Claude in Zellij, verifies, opens PR."""

    name = "code"
    task_type = "code"
    stages = ["triage", "execute", "verify", "deliver"]
    connectors = ["github", "onepassword"]

    def __init__(
        self,
        workspace_dir: str = "/home/thomaseckert/Repos",
        claude_model: str = "claude-sonnet-4-20250514",
        claude_timeout: int = 300,
    ):
        self._git = GitOps(workspace_dir)
        self._zellij = ZellijRunner(model=claude_model, timeout=claude_timeout)

    async def triage(self, task: Task, ctx: AgentContext) -> bool:
        if not task.repo:
            logger.warning("Task %s has no repo, cannot handle", task.id)
            return False
        return True

    async def execute(self, task: Task, ctx: AgentContext) -> dict:
        repo_url = f"https://github.com/{task.repo}.git"
        branch_name = f"forge/{task.id[:12]}"
        session_name = f"agent-{task.id}"

        repo_path = await self._git.ensure_repo(repo_url, task.repo)
        worktree_path = await self._git.create_worktree(repo_path, branch_name)

        prompt = build_prompt(
            title=task.title,
            description=task.description,
            repo=task.repo,
        )

        retry_context = None
        output = ""

        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                logger.info("Retry %d/%d for task %s", attempt, MAX_RETRIES, task.id)
                prompt = build_prompt(
                    title=task.title,
                    description=task.description,
                    repo=task.repo,
                    retry_context=retry_context,
                )

            try:
                output = await self._zellij.run(
                    prompt, worktree_path, session_name=session_name
                )
            except (TimeoutError, RuntimeError) as e:
                retry_context = f"Attempt {attempt + 1} failed: {e}"
                if attempt == MAX_RETRIES:
                    raise
                continue

            break

        return {
            "worktree_path": worktree_path,
            "repo_path": repo_path,
            "branch_name": branch_name,
            "claude_output": output[:2000],
            "zellij_session": session_name,
            "attach_cmd": f"ssh box -t zellij attach {session_name}",
        }

    async def verify(self, task: Task, ctx: AgentContext) -> bool:
        worktree_path = task.handler_data.get("worktree_path")
        if not worktree_path:
            logger.error("No worktree_path in handler_data for task %s", task.id)
            return False
        result = await run_verification(worktree_path)
        return result.success

    async def deliver(self, task: Task, ctx: AgentContext) -> dict:
        worktree_path = task.handler_data.get("worktree_path")
        repo_path = task.handler_data.get("repo_path")
        branch_name = task.handler_data.get("branch_name", "")
        session_name = task.handler_data.get("zellij_session", "")

        if not worktree_path or not repo_path:
            return {"status": "delivered", "error": "Missing worktree or repo path"}

        try:
            diff = await self._git.get_diff(worktree_path, "main")
        except RuntimeError:
            diff = "(diff unavailable)"

        title = f"forge: {task.title}"
        body_parts = [
            f"## Task\n{task.description}",
            f"\n## Source\n{task.source.value}",
        ]
        if task.source_id:
            body_parts.append(f"Linear: {task.source_id}")
        body_parts.append("\n---\nAutomated by Ardent Forge")
        body = "\n".join(body_parts)

        try:
            pr_url = await self._git.create_pr(worktree_path, title, body)
        except RuntimeError as e:
            logger.error("PR creation failed: %s", e)
            pr_url = f"PR creation failed: {e}"

        try:
            await self._git.cleanup_worktree(repo_path, worktree_path)
        except RuntimeError:
            logger.warning("Failed to cleanup worktree %s", worktree_path)

        result: dict = {
            "status": "delivered",
            "pr_url": pr_url,
            "branch": branch_name,
        }
        if session_name:
            result["attach_cmd"] = f"ssh box -t zellij attach {session_name}"
        return result
