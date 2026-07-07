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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from forge.connectors import Connector, Tool
from forge.notebook import NotebookReader, NotebookWriter, analysis
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

    def __init__(self, root: Path, tz: str = "America/Toronto"):
        self._root = root
        self._reader: NotebookReader | None = None
        self._writer: NotebookWriter | None = None
        try:
            self._tz: ZoneInfo | None = ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            logger.warning("Unknown timezone %r; falling back to system local time", tz)
            self._tz = None

    def _now(self) -> datetime:
        """Current wall-clock time in the configured timezone, as a naive
        datetime — a drop-in for datetime.now() so "today" tracks the user's
        local day instead of the server's (UTC) day near midnight."""
        return datetime.now(self._tz).replace(tzinfo=None)

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
                {"path": h.path, "line_number": h.line_number, "line": h.line} for h in capped
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
            date = self._now().strftime("%Y-%m-%d")
        log_path = f"Log/{date}.md"
        try:
            content = await asyncio.to_thread(r.read, log_path)
        except FileNotFoundError:
            return {"error": f"No log entry for {date}", "path": log_path}
        except ValueError as exc:
            return {"error": str(exc)}
        return {"date": date, "path": log_path, "content": content}

    # The log-analysis tools delegate to forge.notebook.analysis; the connector
    # only resolves reader/writer availability and "today" in the user's tz.

    async def _draft_log(self, date: str | None = None) -> dict[str, Any]:
        r = self._require_reader()
        if isinstance(r, dict):
            return r
        w = self._require_writer()
        if isinstance(w, dict):
            return w
        target_date = datetime.strptime(date, "%Y-%m-%d") if date else self._now()
        return await analysis.draft_log(r, w, target_date)

    async def _week_review(self, end_date: str | None = None, days: int = 7) -> dict[str, Any]:
        r = self._require_reader()
        if isinstance(r, dict):
            return r
        end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else self._now()
        return await analysis.week_review(r, end, days)

    async def _stalled_work(self, lookback_days: int = 14) -> dict[str, Any]:
        r = self._require_reader()
        if isinstance(r, dict):
            return r
        return await analysis.stalled_work(r, self._now(), lookback_days)

    async def _summarize_log(self, date: str | None = None) -> dict[str, Any]:
        r = self._require_reader()
        if isinstance(r, dict):
            return r
        if date is None:
            date = self._now().strftime("%Y-%m-%d")
        return await analysis.summarize_log(r, date)

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
