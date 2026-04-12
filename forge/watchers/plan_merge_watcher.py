import logging
from pathlib import Path
from typing import Awaitable, Callable

from forge.frontmatter import SpecStatus, read_spec
from forge.models import Task, TaskSource, TaskType

logger = logging.getLogger(__name__)


class PlanMergeWatcher:
    def __init__(
        self,
        store,
        repo_path: str,
        plans_subdir: str = "docs/superpowers/plans",
        specs_subdir: str = "docs/superpowers/specs",
        fetch_fn: Callable[[], Awaitable[None]] | None = None,
        self_repo: str = "t-eckert/ardent-forge",
    ):
        self._store = store
        self._repo_path = Path(repo_path)
        self._plans_subdir = plans_subdir
        self._specs_subdir = specs_subdir
        self._fetch = fetch_fn
        self._self_repo = self_repo

    async def poll(self) -> int:
        if self._fetch:
            try:
                await self._fetch()
            except Exception:
                logger.exception("plan-merge watcher fetch failed")

        plans_dir = self._repo_path / self._plans_subdir
        specs_dir = self._repo_path / self._specs_subdir
        if not plans_dir.is_dir() or not specs_dir.is_dir():
            return 0

        created = 0
        for plan_abs in sorted(plans_dir.glob("*.md")):
            spec_abs = specs_dir / plan_abs.name
            if not spec_abs.exists():
                continue
            parsed = read_spec(spec_abs)
            if parsed.status != SpecStatus.PLANNED:
                continue

            plan_rel = str(plan_abs.relative_to(self._repo_path))
            spec_rel = str(spec_abs.relative_to(self._repo_path))
            source_id = f"plan:{plan_rel}"
            if await self._store.find_by_source_id(source_id) is not None:
                continue

            task = Task.new(
                task_type=TaskType.TICKETS,
                source=TaskSource.WEBHOOK,
                title=f"tickets for {plan_abs.stem}",
                description=f"plan: {plan_rel} spec: {spec_rel}",
                source_id=source_id,
                repo=self._self_repo,
            )
            await self._store.save(task)
            logger.info(f"Enqueued tickets task for {plan_rel}")
            created += 1
        return created
