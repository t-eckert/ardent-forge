"""Daily-log analysis over the notebook vault.

Domain logic behind the NotebookConnector's drafting/review tools: template
expansion, deferred-task carry-forward, weekly aggregation, stalled-work
detection, and day summaries. Everything here works through a NotebookReader
(and NotebookWriter for drafting); reads are offloaded to threads because the
reader is sync (ripgrep/filesystem).

Date resolution ("today" in the user's timezone) stays with the caller — these
functions take explicit datetimes.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from typing import Any

from forge.notebook.reader import NotebookReader
from forge.notebook.writer import NotebookWriter


def expand_template(template: str, dt: datetime) -> str:
    """Expand Obsidian Templater date variables."""
    # Strip frontmatter — we'll build a fresh one.
    if template.startswith("---"):
        end = template.find("---", 3)
        if end != -1:
            template = template[end + 3 :].lstrip("\n")

    # Build frontmatter with actual date.
    alias = dt.strftime("%-d %B %Y")
    frontmatter = f'---\naliases:\n  - "{alias}"\n---\n'

    # Replace {{date:FORMAT}} patterns with actual formatted dates.
    def _replace_date(m: re.Match) -> str:
        fmt = m.group(1)
        # Convert Moment.js-style format to strftime.
        conversions = {
            "ddd": dt.strftime("%a"),
            "D": str(dt.day),
            "MMMM": dt.strftime("%B"),
            "YYYY": dt.strftime("%Y"),
            "MM": dt.strftime("%m"),
            "DD": dt.strftime("%d"),
        }
        result = fmt
        # Replace longest tokens first to avoid partial matches.
        for token, value in sorted(conversions.items(), key=lambda x: -len(x[0])):
            result = result.replace(token, value)
        return result

    body = re.sub(r"\{\{date:(.*?)\}\}", _replace_date, template)
    return frontmatter + body


async def extract_deferred_tasks(reader: NotebookReader, log_path: str) -> list[str]:
    """Extract tasks marked [>] from a log file."""
    try:
        content = await asyncio.to_thread(reader.read, log_path)
    except (FileNotFoundError, ValueError):
        return []
    deferred: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [>]"):
            task_text = stripped[5:].strip()
            if task_text:
                deferred.append(task_text)
    return deferred


async def draft_log(
    reader: NotebookReader, writer: NotebookWriter, target_date: datetime
) -> dict[str, Any]:
    """Draft a daily log from the template, carrying forward yesterday's
    deferred tasks. Refuses to overwrite an existing log."""
    date_str = target_date.strftime("%Y-%m-%d")
    log_path = f"Log/{date_str}.md"

    # Don't overwrite an existing log.
    if await asyncio.to_thread(reader.exists, log_path):
        return {"error": f"Log already exists: {log_path}", "path": log_path}

    # Read template.
    template_path = "+Templates/Daily Note.md"
    try:
        template = await asyncio.to_thread(reader.read, template_path)
    except FileNotFoundError:
        template = None

    # Expand template date variables.
    if template:
        content = expand_template(template, target_date)
    else:
        heading = target_date.strftime("%a %d %B %Y")
        content = f"# {heading}\n\n## Work\n\n## Personal\n\n## Notes\n"

    # Carry forward deferred tasks from yesterday.
    yesterday = target_date - timedelta(days=1)
    yesterday_path = f"Log/{yesterday.strftime('%Y-%m-%d')}.md"
    deferred = await extract_deferred_tasks(reader, yesterday_path)
    if deferred:
        content += (
            "\n## Carried forward\n\n" + "\n".join(f"- [ ] {task}" for task in deferred) + "\n"
        )

    # Write the draft.
    try:
        await asyncio.to_thread(writer.write, log_path, content)
    except Exception as exc:
        return {"error": f"write failed: {exc}"}

    return {
        "path": log_path,
        "date": date_str,
        "deferred_count": len(deferred),
        "status": "drafted",
    }


async def week_review(reader: NotebookReader, end: datetime, days: int = 7) -> dict[str, Any]:
    """Aggregate task stats and wikilink mentions across a range of daily logs."""
    days = max(1, min(days, 90))

    all_completed: list[str] = []
    all_deferred: list[str] = []
    all_open: list[str] = []
    people_mentioned: dict[str, int] = {}
    logs_found: list[str] = []
    logs_missing: list[str] = []

    for i in range(days):
        day = end - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        log_path = f"Log/{day_str}.md"
        try:
            content = await asyncio.to_thread(reader.read, log_path)
        except (FileNotFoundError, ValueError):
            logs_missing.append(day_str)
            continue
        logs_found.append(day_str)

        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("- [x]"):
                all_completed.append(stripped[5:].strip())
            elif stripped.startswith("- [>]"):
                all_deferred.append(stripped[5:].strip())
            elif stripped.startswith("- [ ]"):
                all_open.append(stripped[5:].strip())

            # Extract [[wikilink]] mentions — likely people or projects.
            for match in re.finditer(r"\[\[([^\]]+)\]\]", line):
                name = match.group(1)
                people_mentioned[name] = people_mentioned.get(name, 0) + 1

    # Sort people by mention count.
    top_mentions = sorted(people_mentioned.items(), key=lambda x: -x[1])[:20]

    return {
        "period": {
            "start": (end - timedelta(days=days - 1)).strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "days": days,
        },
        "logs_found": len(logs_found),
        "logs_missing": len(logs_missing),
        "tasks": {
            "completed": len(all_completed),
            "deferred": len(all_deferred),
            "still_open": len(all_open),
            "completed_list": all_completed[:30],
            "deferred_list": all_deferred[:20],
        },
        "mentions": [{"name": n, "count": c} for n, c in top_mentions],
    }


async def stalled_work(
    reader: NotebookReader, today: datetime, lookback_days: int = 14
) -> dict[str, Any]:
    """Find rolling deferrals ([>] in 3+ logs) and projects absent from recent logs."""
    lookback_days = max(1, min(lookback_days, 90))

    # 1. Find rolling deferrals — tasks that appear as [>] in multiple logs.
    deferral_counts: dict[str, int] = {}
    for i in range(lookback_days):
        day = today - timedelta(days=i)
        log_path = f"Log/{day.strftime('%Y-%m-%d')}.md"
        deferred = await extract_deferred_tasks(reader, log_path)
        for task in deferred:
            # Normalize whitespace for dedup.
            key = " ".join(task.split())
            deferral_counts[key] = deferral_counts.get(key, 0) + 1

    rolling_deferrals = [
        {"task": task, "times_deferred": count}
        for task, count in sorted(deferral_counts.items(), key=lambda x: -x[1])
        if count >= 3
    ]

    # 2. Find stalled projects — projects not mentioned in recent logs.
    projects_dir = "Projects"
    active_projects: list[str] = []
    try:
        entries = await asyncio.to_thread(reader.list_dir, projects_dir)
        for entry in entries:
            # Skip special subdirs.
            if entry.startswith("+"):
                continue
            active_projects.append(entry.removesuffix(".md"))
    except (NotADirectoryError, ValueError):
        pass

    # Scan logs for project mentions.
    mentioned_projects: set[str] = set()
    for i in range(lookback_days):
        day = today - timedelta(days=i)
        log_path = f"Log/{day.strftime('%Y-%m-%d')}.md"
        try:
            content = await asyncio.to_thread(reader.read, log_path)
        except (FileNotFoundError, ValueError):
            continue
        for proj in active_projects:
            if proj in content:
                mentioned_projects.add(proj)

    stalled_projects = [p for p in active_projects if p not in mentioned_projects]

    return {
        "lookback_days": lookback_days,
        "rolling_deferrals": rolling_deferrals,
        "stalled_projects": stalled_projects,
        "active_project_count": len(active_projects),
    }


async def summarize_log(reader: NotebookReader, date: str) -> dict[str, Any]:
    """Bucket a day's tasks by checkbox state: completed/deferred/open/partial/dropped."""
    log_path = f"Log/{date}.md"
    try:
        content = await asyncio.to_thread(reader.read, log_path)
    except FileNotFoundError:
        return {"error": f"No log entry for {date}", "path": log_path}
    except ValueError as exc:
        return {"error": str(exc)}

    completed: list[str] = []
    deferred: list[str] = []
    open_tasks: list[str] = []
    partial: list[str] = []
    dropped: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [x]"):
            completed.append(stripped[5:].strip())
        elif stripped.startswith("- [>]"):
            deferred.append(stripped[5:].strip())
        elif stripped.startswith("- [ ]"):
            open_tasks.append(stripped[5:].strip())
        elif stripped.startswith("- [~]"):
            partial.append(stripped[5:].strip())
        elif stripped.startswith("- [!]"):
            dropped.append(stripped[5:].strip())

    total = len(completed) + len(deferred) + len(open_tasks) + len(partial) + len(dropped)
    return {
        "date": date,
        "path": log_path,
        "completed": completed,
        "deferred": deferred,
        "open": open_tasks,
        "partial": partial,
        "dropped": dropped,
        "total_tasks": total,
        "completion_rate": f"{len(completed)}/{total}" if total else "no tasks",
    }
