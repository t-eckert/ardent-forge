from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import frontmatter


class SpecStatus(StrEnum):
    DRAFT = "draft"
    READY_TO_PLAN = "ready-to-plan"
    PLANNED = "planned"
    EXECUTING = "executing"
    DONE = "done"


@dataclass
class ParsedSpec:
    path: Path
    status: SpecStatus | None
    title: str | None
    body: str
    raw: dict


def read_spec(path: Path) -> ParsedSpec:
    post = frontmatter.load(str(path))
    raw_status = post.metadata.get("status")
    try:
        status = SpecStatus(raw_status) if raw_status else None
    except ValueError:
        status = None
    return ParsedSpec(
        path=path,
        status=status,
        title=post.metadata.get("title"),
        body=post.content,
        raw=dict(post.metadata),
    )


def update_spec_status(path: Path, status: SpecStatus) -> None:
    post = frontmatter.load(str(path))
    post["status"] = status.value
    with open(path, "wb") as f:
        frontmatter.dump(post, f)


def find_specs_by_status(root: Path, status: SpecStatus) -> list[Path]:
    results: list[Path] = []
    for md in sorted(root.glob("*.md")):
        try:
            parsed = read_spec(md)
        except Exception:
            continue
        if parsed.status == status:
            results.append(md)
    return results
