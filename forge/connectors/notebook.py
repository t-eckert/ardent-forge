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
                name="notebook_write",
                description=(
                    "Write (overwrite) a note in the Notebook vault. Paths must start "
                    "with 'Wiki/', 'Fields/', or 'Log/' — enforced at the write boundary. "
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
