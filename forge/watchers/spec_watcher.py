import logging
from pathlib import Path
from typing import Awaitable, Callable

from forge.frontmatter import SpecStatus, find_specs_by_status
from forge.models import Task, TaskSource, TaskType

logger = logging.getLogger(__name__)


class SpecWatcher:
    def __init__(
        self,
        store,
        repo_path: str,
        specs_subdir: str = "docs/superpowers/specs",
        fetch_fn: Callable[[], Awaitable[None]] | None = None,
        self_repo: str = "t-eckert/ardent-forge",
    ):
        self._store = store
        self._repo_path = Path(repo_path)
        self._specs_subdir = specs_subdir
        self._fetch = fetch_fn
        self._self_repo = self_repo

    async def poll(self) -> int:
        if self._fetch:
            try:
                await self._fetch()
            except Exception:
                logger.exception("spec watcher fetch failed; proceeding with local state")

        specs_dir = self._repo_path / self._specs_subdir
        if not specs_dir.is_dir():
            return 0

        ready = find_specs_by_status(specs_dir, SpecStatus.READY_TO_PLAN)
        created = 0
        for spec_abs in ready:
            rel = str(spec_abs.relative_to(self._repo_path))
            source_id = f"spec:{rel}"
            if await self._store.find_by_source_id(source_id) is not None:
                continue
            task = Task.new(
                task_type=TaskType.PLAN,
                source=TaskSource.WEBHOOK,
                title=f"plan {spec_abs.stem}",
                description=f"spec: {rel}",
                source_id=source_id,
                repo=self._self_repo,
            )
            await self._store.save(task)
            logger.info(f"Enqueued plan task for {rel}")
            created += 1
        return created
