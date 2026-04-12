import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

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
