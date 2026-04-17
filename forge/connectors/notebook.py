"""NotebookConnector — Obsidian vault wrapped as a Connector.

Exposes the NotebookReader + NotebookWriter primitives as tools so both
Forge (in chat) and agents (via the 'notebook' connector declaration)
can read, search, and write notes through the same surface.

Writes are guarded by NotebookWriter's ALLOWED_WRITE_PREFIXES — paths
outside Wiki/, Fields/, Log/ are rejected at the boundary with a helpful
error message that surfaces back to Claude.

See docs/superpowers/specs/2026-04-12-notebook-integration-design.md.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from forge.connectors import Connector, Tool
from forge.notebook import NotebookReader, NotebookWriter
from forge.notebook.errors import NotebookWriteError

logger = logging.getLogger(__name__)

# Search results cap — ripgrep on a big vault can spew thousands of lines.
# 50 is enough for Claude to reason about; anything more should be narrowed
# with a path_prefix.
MAX_SEARCH_HITS = 50
# Soft cap on list_dir entries returned per call.
MAX_LIST_ENTRIES = 200


class NotebookConnector(Connector):
    name = "notebook"

    def __init__(self, root: Path):
        self._root = root
        self._reader: NotebookReader | None = None
        self._writer: NotebookWriter | None = None

    async def setup(self) -> None:
        # NotebookReader/Writer constructors are sync and validate that the
        # root exists + rg is available. Instantiate lazily so a missing
        # notebook during startup doesn't crash the whole process — the
        # connector just reports unhealthy until the vault appears.
        try:
            self._reader = NotebookReader(self._root)
            self._writer = NotebookWriter(self._root)
        except Exception:
            logger.exception("NotebookConnector setup failed for %s", self._root)
            self._reader = None
            self._writer = None

    async def health(self) -> bool:
        return self._reader is not None and self._root.is_dir()

    @property
    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="notebook_search",
                description=(
                    "Search the Notebook vault for text. Use when the user "
                    "asks what they've written about a topic, or when an agent "
                    "needs existing context before writing new notes. Returns "
                    "up to 50 matching lines with file paths and line numbers."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Literal or regex pattern (ripgrep syntax).",
                        },
                        "path_prefix": {
                            "type": "string",
                            "description": "Optional subdirectory scope, e.g. 'Wiki' or 'Fields/Health'.",
                        },
                    },
                    "required": ["query"],
                },
                execute=self._search,
                connector_name=self.name,
            ),
            Tool(
                name="notebook_read",
                description=(
                    "Read a single note by path (relative to the Notebook root). "
                    "Use this to pull an existing note's full text into context."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path, e.g. 'Wiki/Svelte 5 Breaking Changes.md'.",
                        }
                    },
                    "required": ["path"],
                },
                execute=self._read,
                connector_name=self.name,
            ),
            Tool(
                name="notebook_list",
                description=(
                    "List entries (files + subdirectories) in a Notebook directory. "
                    "Omit path for the vault root."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path. Omit for the root.",
                        }
                    },
                },
                execute=self._list,
                connector_name=self.name,
            ),
            Tool(
                name="notebook_resolve_wikilink",
                description=(
                    "Resolve an Obsidian wikilink (e.g. [[Svelte 5]]) to a concrete "
                    "path under the vault. Returns the shortest matching path, matching "
                    "Obsidian's resolution behaviour."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Note name without .md"}
                    },
                    "required": ["name"],
                },
                execute=self._resolve_wikilink,
                connector_name=self.name,
            ),
            Tool(
                name="notebook_recent",
                description=(
                    "List the most recently modified notes, optionally scoped "
                    "to a section (e.g. 'Log', 'Fields/Health', 'Projects'). "
                    "Useful for understanding what's been active lately."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "section": {
                            "type": "string",
                            "description": "Subdirectory to scope to, e.g. 'Log' or 'Fields'. Omit for whole vault.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 20, max 50).",
                        },
                    },
                },
                execute=self._recent,
                connector_name=self.name,
            ),
            Tool(
                name="notebook_log",
                description=(
                    "Read a daily log entry by date. Convenience wrapper: "
                    "pass a date like '2026-04-16' and get the Log file content. "
                    "Omit date for today's log."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "ISO date (YYYY-MM-DD). Omit for today.",
                        },
                    },
                },
                execute=self._log,
                connector_name=self.name,
            ),
            Tool(
                name="notebook_draft_log",
                description=(
                    "Draft today's daily log from the template, carrying forward "
                    "deferred tasks from yesterday. Only creates the file if it "
                    "doesn't already exist. Returns the drafted content and path."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "ISO date (YYYY-MM-DD). Omit for today.",
                        },
                    },
                },
                execute=self._draft_log,
                connector_name=self.name,
            ),
            Tool(
                name="notebook_week_review",
                description=(
                    "Gather data for a weekly review: read all daily logs in a "
                    "date range (defaults to last 7 days), aggregate task stats, "
                    "people mentioned, and sections active. Returns structured "
                    "data for Forge to narrate — does not write anything."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "end_date": {
                            "type": "string",
                            "description": "End date (YYYY-MM-DD). Defaults to today.",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days to cover (default 7).",
                        },
                    },
                },
                execute=self._week_review,
                connector_name=self.name,
            ),
            Tool(
                name="notebook_stalled_work",
                description=(
                    "Detect stalled projects and rolling deferrals. Scans recent "
                    "daily logs for tasks that keep getting deferred, and checks "
                    "which projects haven't been referenced in logs recently. "
                    "Returns structured findings for Forge to present gently."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "lookback_days": {
                            "type": "integer",
                            "description": "How many days of logs to scan (default 14).",
                        },
                    },
                },
                execute=self._stalled_work,
                connector_name=self.name,
            ),
            Tool(
                name="notebook_summarize_log",
                description=(
                    "Summarize a day's log: what was planned vs. what happened. "
                    "Lists completed, deferred, and open tasks. Use for evening "
                    "shutdown or on-demand review of any day. Does NOT write — "
                    "returns the summary for Forge to present or append."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "ISO date (YYYY-MM-DD). Omit for today.",
                        },
                    },
                },
                execute=self._summarize_log,
                connector_name=self.name,
            ),
            Tool(
                name="notebook_write",
                description=(
                    "Write (overwrite) a note in the Notebook vault. Paths must start "
                    "with an allowed prefix (Wiki/, Fields/, Log/, People/, Projects/) "
                    "— enforced at the write boundary. "
                    "Use for creating or updating a note; use notebook_append for log-style "
                    "additions that shouldn't replace existing content."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path under an allowed prefix."},
                        "content": {"type": "string", "description": "Full file content."},
                    },
                    "required": ["path", "content"],
                },
                execute=self._write,
                connector_name=self.name,
                long_running=False,
            ),
            Tool(
                name="notebook_append",
                description=(
                    "Append content to an existing note. Same path allowlist as "
                    "notebook_write. Good for log entries and running notes."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
                execute=self._append,
                connector_name=self.name,
            ),
        ]

    # ─── Tool implementations ──────────────────────────────────────────

    def _require_reader(self) -> NotebookReader | dict:
        if self._reader is None:
            return {"error": "Notebook not configured or unavailable"}
        return self._reader

    def _require_writer(self) -> NotebookWriter | dict:
        if self._writer is None:
            return {"error": "Notebook not configured or unavailable"}
        return self._writer

    async def _search(self, query: str, path_prefix: str | None = None) -> dict[str, Any]:
        r = self._require_reader()
        if isinstance(r, dict):
            return r
        try:
            # NotebookReader.search is sync (ripgrep subprocess); offload to a
            # thread so we don't block the event loop.
            hits = await asyncio.to_thread(r.search, query, path_prefix)
        except Exception as exc:
            return {"error": f"search failed: {exc}"}
        capped = hits[:MAX_SEARCH_HITS]
        return {
            "hits": [
                {"path": h.path, "line_number": h.line_number, "line": h.line}
                for h in capped
            ],
            "total": len(hits),
            "truncated": len(hits) > MAX_SEARCH_HITS,
        }

    async def _read(self, path: str) -> dict[str, Any]:
        r = self._require_reader()
        if isinstance(r, dict):
            return r
        try:
            content = await asyncio.to_thread(r.read, path)
        except FileNotFoundError:
            return {"error": f"note not found: {path}"}
        except ValueError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"read failed: {exc}"}
        return {"path": path, "content": content}

    async def _list(self, path: str | None = None) -> dict[str, Any]:
        r = self._require_reader()
        if isinstance(r, dict):
            return r
        try:
            entries = await asyncio.to_thread(r.list_dir, path or "")
        except (NotADirectoryError, ValueError) as exc:
            return {"error": str(exc)}
        capped = sorted(entries)[:MAX_LIST_ENTRIES]
        return {
            "path": path or "",
            "entries": capped,
            "total": len(entries),
            "truncated": len(entries) > MAX_LIST_ENTRIES,
        }

    async def _resolve_wikilink(self, name: str) -> dict[str, Any]:
        r = self._require_reader()
        if isinstance(r, dict):
            return r
        match = await asyncio.to_thread(r.resolve_wikilink, name)
        return {"name": name, "path": str(match) if match else None}

    async def _recent(self, section: str | None = None, limit: int = 20) -> dict[str, Any]:
        r = self._require_reader()
        if isinstance(r, dict):
            return r
        limit = min(max(limit, 1), 50)
        try:
            entries = await asyncio.to_thread(r.recent, section or "", limit)
        except (NotADirectoryError, ValueError) as exc:
            return {"error": str(exc)}
        return {
            "section": section or "(all)",
            "entries": [
                {
                    "path": path,
                    "modified": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
                }
                for path, mtime in entries
            ],
        }

    async def _log(self, date: str | None = None) -> dict[str, Any]:
        r = self._require_reader()
        if isinstance(r, dict):
            return r
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        log_path = f"Log/{date}.md"
        try:
            content = await asyncio.to_thread(r.read, log_path)
        except FileNotFoundError:
            return {"error": f"No log entry for {date}", "path": log_path}
        except ValueError as exc:
            return {"error": str(exc)}
        return {"date": date, "path": log_path, "content": content}

    async def _draft_log(self, date: str | None = None) -> dict[str, Any]:
        r = self._require_reader()
        if isinstance(r, dict):
            return r
        w = self._require_writer()
        if isinstance(w, dict):
            return w

        target_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
        date_str = target_date.strftime("%Y-%m-%d")
        log_path = f"Log/{date_str}.md"

        # Don't overwrite an existing log.
        if await asyncio.to_thread(r.exists, log_path):
            return {"error": f"Log already exists: {log_path}", "path": log_path}

        # Read template.
        template_path = "+Templates/Daily Note.md"
        try:
            template = await asyncio.to_thread(r.read, template_path)
        except FileNotFoundError:
            template = None

        # Expand template date variables.
        if template:
            content = self._expand_template(template, target_date)
        else:
            heading = target_date.strftime("%a %d %B %Y")
            content = f"# {heading}\n\n## Work\n\n## Personal\n\n## Notes\n"

        # Carry forward deferred tasks from yesterday.
        yesterday = target_date - timedelta(days=1)
        yesterday_path = f"Log/{yesterday.strftime('%Y-%m-%d')}.md"
        deferred = await self._extract_deferred_tasks(r, yesterday_path)
        if deferred:
            content += "\n## Carried forward\n\n" + "\n".join(
                f"- [ ] {task}" for task in deferred
            ) + "\n"

        # Write the draft.
        try:
            await asyncio.to_thread(w.write, log_path, content)
        except Exception as exc:
            return {"error": f"write failed: {exc}"}

        return {
            "path": log_path,
            "date": date_str,
            "deferred_count": len(deferred),
            "status": "drafted",
        }

    @staticmethod
    def _expand_template(template: str, dt: datetime) -> str:
        """Expand Obsidian Templater date variables."""
        # Strip frontmatter — we'll build a fresh one.
        if template.startswith("---"):
            end = template.find("---", 3)
            if end != -1:
                template = template[end + 3:].lstrip("\n")

        # Build frontmatter with actual date.
        alias = dt.strftime("%-d %B %Y")
        frontmatter = f"---\naliases:\n  - \"{alias}\"\n---\n"

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

    @staticmethod
    async def _extract_deferred_tasks(reader: "NotebookReader", log_path: str) -> list[str]:
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

    async def _week_review(self, end_date: str | None = None, days: int = 7) -> dict[str, Any]:
        r = self._require_reader()
        if isinstance(r, dict):
            return r

        end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
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
                content = await asyncio.to_thread(r.read, log_path)
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

    async def _stalled_work(self, lookback_days: int = 14) -> dict[str, Any]:
        r = self._require_reader()
        if isinstance(r, dict):
            return r

        lookback_days = max(1, min(lookback_days, 90))
        today = datetime.now()

        # 1. Find rolling deferrals — tasks that appear as [>] in multiple logs.
        deferral_counts: dict[str, int] = {}
        for i in range(lookback_days):
            day = today - timedelta(days=i)
            log_path = f"Log/{day.strftime('%Y-%m-%d')}.md"
            deferred = await self._extract_deferred_tasks(r, log_path)
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
            entries = await asyncio.to_thread(r.list_dir, projects_dir)
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
                content = await asyncio.to_thread(r.read, log_path)
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

    async def _summarize_log(self, date: str | None = None) -> dict[str, Any]:
        r = self._require_reader()
        if isinstance(r, dict):
            return r
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        log_path = f"Log/{date}.md"
        try:
            content = await asyncio.to_thread(r.read, log_path)
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

    async def _write(self, path: str, content: str) -> dict[str, Any]:
        w = self._require_writer()
        if isinstance(w, dict):
            return w
        try:
            await asyncio.to_thread(w.write, path, content)
        except NotebookWriteError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"write failed: {exc}"}
        return {"path": path, "bytes": len(content), "status": "ok"}

    async def _append(self, path: str, content: str) -> dict[str, Any]:
        w = self._require_writer()
        if isinstance(w, dict):
            return w
        try:
            await asyncio.to_thread(w.append, path, content)
        except NotebookWriteError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"append failed: {exc}"}
        return {"path": path, "bytes": len(content), "status": "ok"}
