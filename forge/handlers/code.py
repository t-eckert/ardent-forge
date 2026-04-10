import logging

from forge.claude import ClaudeRunner, build_prompt
from forge.git import GitOps
from forge.models import Task
from forge.verify import run_verification

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


class CodeHandler:
    task_type: str = "code"

    def __init__(
        self,
        workspace_dir: str = "/var/lib/ardent-forge/repos",
        claude_model: str = "claude-sonnet-4-20250514",
        claude_timeout: int = 300,
    ):
        self._git = GitOps(workspace_dir)
        self._claude = ClaudeRunner(model=claude_model, timeout=claude_timeout)

    async def triage(self, task: Task) -> bool:
        if not task.repo:
            logger.warning(f"Task {task.id} has no repo, cannot handle")
            return False
        return True

    async def execute(self, task: Task) -> dict:
        repo_url = f"https://github.com/{task.repo}.git"
        branch_name = f"forge/{task.id[:12]}"

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
                logger.info(f"Retry {attempt}/{MAX_RETRIES} for task {task.id}")
                prompt = build_prompt(
                    title=task.title,
                    description=task.description,
                    repo=task.repo,
                    retry_context=retry_context,
                )

            try:
                output = await self._claude.run(prompt, worktree_path)
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
        }

    async def verify(self, task: Task) -> bool:
        worktree_path = task.handler_data.get("worktree_path")
        if not worktree_path:
            logger.error(f"No worktree_path in handler_data for task {task.id}")
            return False
        result = await run_verification(worktree_path)
        return result.success

    async def deliver(self, task: Task) -> dict:
        worktree_path = task.handler_data.get("worktree_path")
        repo_path = task.handler_data.get("repo_path")
        branch_name = task.handler_data.get("branch_name", "")

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
        }
