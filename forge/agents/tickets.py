import logging
import re
from dataclasses import dataclass
from pathlib import Path

from forge.agents import AgentContext, record_triage_reason
from forge.frontmatter import SpecStatus, update_spec_status
from forge.git import GitOps
from forge.guardrails import check_handler_allowlist
from forge.models import Task

logger = logging.getLogger(__name__)

PLAN_PATH_RE = re.compile(r"plan:\s*(docs/superpowers/plans/[\w\-.]+\.md)")
SPEC_PATH_RE = re.compile(r"spec:\s*(docs/superpowers/specs/[\w\-.]+\.md)")

TASK_HEADER_RE = re.compile(r"^## Task (\d+): (.+?)$", re.MULTILINE)


@dataclass
class PlanTask:
    number: int
    title: str
    body: str


def parse_plan_tasks(plan_markdown: str) -> list[PlanTask]:
    matches = list(TASK_HEADER_RE.finditer(plan_markdown))
    results: list[PlanTask] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(plan_markdown)
        body = plan_markdown[start:end].strip()
        body = re.split(r"\n---\n", body, maxsplit=1)[0].strip()
        results.append(
            PlanTask(number=int(m.group(1)), title=m.group(2).strip(), body=body)
        )
    return results


def extract_plan_path(description: str) -> str | None:
    m = PLAN_PATH_RE.search(description or "")
    return m.group(1) if m else None


def extract_spec_path_from_tickets_task(description: str) -> str | None:
    m = SPEC_PATH_RE.search(description or "")
    return m.group(1) if m else None


class TicketsAgent:
    name = "tickets"
    task_type = "tickets"
    stages = ["triage", "execute", "verify", "deliver"]
    connectors = ["linear"]

    def __init__(
        self,
        workspace_dir: str,
        linear,
        team_id: str,
        self_repo: str = "t-eckert/ardent-forge",
        label: str = "devagent",
    ):
        self._git = GitOps(workspace_dir)
        self._linear = linear
        self._team_id = team_id
        self._self_repo = self_repo
        self._label = label

    async def triage(self, task: Task, ctx: AgentContext) -> bool:
        if extract_plan_path(task.description) is None:
            await record_triage_reason(
                ctx,
                task,
                "No plan path found in the task description. A tickets task needs "
                "a `plan:` reference to a plan under docs/superpowers/plans/.",
            )
            return False
        return True

    async def execute(self, task: Task, ctx: AgentContext) -> dict:
        plan_rel = extract_plan_path(task.description)
        spec_rel = extract_spec_path_from_tickets_task(task.description)
        if not plan_rel or not spec_rel:
            raise RuntimeError(f"Task {task.id} missing plan or spec path")

        repo_url = f"https://github.com/{self._self_repo}.git"
        repo_path = await self._git.ensure_repo(repo_url, self._self_repo)

        await self._git._run("git fetch origin main", cwd=repo_path)
        await self._git._run("git checkout main", cwd=repo_path)
        await self._git._run("git reset --hard origin/main", cwd=repo_path)

        plan_abs = Path(repo_path) / plan_rel
        spec_abs = Path(repo_path) / spec_rel
        if not plan_abs.exists() or not spec_abs.exists():
            raise RuntimeError("plan or spec file missing in repo clone")

        plan_markdown = plan_abs.read_text()
        plan_tasks = parse_plan_tasks(plan_markdown)
        if not plan_tasks:
            raise RuntimeError(f"No tasks parsed from {plan_rel}")

        project_name = f"{task.title} ({spec_abs.stem})"
        project_desc = f"Generated from {plan_rel}\nSpec: {spec_rel}"
        project_id, project_url = await self._linear.create_project(
            team_id=self._team_id,
            name=project_name,
            description=project_desc,
        )

        label_id = await self._linear.get_label_id(self._team_id, self._label)
        label_ids = [label_id] if label_id else []

        identifiers: list[str] = []
        issue_urls: list[str] = []
        for pt in plan_tasks:
            priority = 2 if pt.number == 1 else 3
            _, identifier, url = await self._linear.create_issue(
                team_id=self._team_id,
                project_id=project_id,
                title=f"{pt.title} (Task {pt.number})",
                description=pt.body + f"\n\n---\nPlan: {plan_rel}\nSpec: {spec_rel}",
                label_ids=label_ids,
                priority=priority,
            )
            identifiers.append(identifier)
            issue_urls.append(url)

        update_spec_status(spec_abs, SpecStatus.EXECUTING)

        return {
            "project_id": project_id,
            "project_url": project_url,
            "issue_identifiers": identifiers,
            "issue_urls": issue_urls,
            "repo_path": repo_path,
            "spec_path": spec_rel,
            "plan_path": plan_rel,
        }

    async def verify(self, task: Task, ctx: AgentContext) -> bool:
        data = task.handler_data
        return bool(data.get("project_id") and data.get("issue_identifiers"))

    async def deliver(self, task: Task, ctx: AgentContext) -> dict:
        repo_path = task.handler_data.get("repo_path")
        spec_rel = task.handler_data.get("spec_path")
        if not repo_path or not spec_rel:
            return {"status": "delivered", "error": "missing repo or spec path"}

        try:
            changed = await self._git.get_working_tree_changes(repo_path)
            violation = check_handler_allowlist(
                handler=self.task_type,
                repo=self._self_repo,
                changed_files=changed,
            )
            if violation:
                raise RuntimeError(violation)

            await self._git.commit_all(repo_path, f"chore: mark {spec_rel} executing")
            await self._git._run("git push origin HEAD:main", cwd=repo_path)
        except RuntimeError as e:
            logger.error(f"tickets deliver failed: {e}")
            return {"status": "delivered", "error": str(e)}

        return {
            "status": "delivered",
            "project_url": task.handler_data.get("project_url"),
            "issue_count": len(task.handler_data.get("issue_identifiers", [])),
        }
