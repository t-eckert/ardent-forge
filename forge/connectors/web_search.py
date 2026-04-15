"""WebSearchConnector — web search via Tavily API.

Exposes a single `web_search` tool that agents and chat can use to find
current information from the web. Tavily is purpose-built for AI agent
search — it returns clean, relevant extracts rather than raw HTML.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from forge.connectors import Connector, Tool

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"


class WebSearchConnector(Connector):
    name = "web_search"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def setup(self) -> None:
        pass

    async def health(self) -> bool:
        return bool(self._api_key)

    @property
    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="web_search",
                description=(
                    "Search the web for current information. Use when the user asks about "
                    "recent events, documentation, people, companies, or anything that may "
                    "have changed since your training data. Returns relevant page titles, "
                    "URLs, and content extracts."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query. Be specific and include context.",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Number of results to return (1-10, default 5).",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
                execute=self._search,
                connector_name=self.name,
            )
        ]

    async def _search(self, query: str, max_results: int = 5) -> dict[str, Any]:
        max_results = max(1, min(10, max_results))
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    TAVILY_API_URL,
                    json={
                        "api_key": self._api_key,
                        "query": query,
                        "max_results": max_results,
                        "include_answer": True,
                        "search_depth": "basic",
                    },
                )
                if resp.status_code != 200:
                    return {"error": f"Search failed (HTTP {resp.status_code})"}
                data = resp.json()
        except Exception as exc:
            logger.exception("Web search failed for query: %s", query)
            return {"error": f"Search unavailable: {exc}"}

        results = []
        for r in data.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
            })

        return {
            "query": query,
            "answer": data.get("answer", ""),
            "results": results,
        }
