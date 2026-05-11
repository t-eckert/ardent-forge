"""SpeedtestConnector — periodic internet bandwidth measurement.

Exposes two tools:

* ``run_speedtest`` — run an on-demand speed test and store the result
* ``get_speedtest_history`` — retrieve recent results from the database

The connector also acts as a poller: when ``poll()`` is called by the
coordinator tick loop, it checks whether enough time has elapsed since
the last test and runs one if so.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import ulid

from forge.connectors import Connector, Tool
from forge.db import Database

logger = logging.getLogger(__name__)


async def _run_speedtest() -> dict[str, Any]:
    """Run speedtest-cli in a thread to avoid blocking the event loop.

    Returns a dict with download_mbps, upload_mbps, ping_ms, server_name,
    and server_location — or a dict with an "error" key on failure.
    """

    def _blocking() -> dict[str, Any]:
        import speedtest as st

        s = st.Speedtest()
        s.get_best_server()
        s.download()
        s.upload()
        result = s.results.dict()
        return {
            "download_mbps": round(result["download"] / 1_000_000, 2),
            "upload_mbps": round(result["upload"] / 1_000_000, 2),
            "ping_ms": round(result["ping"], 2),
            "server_name": result.get("server", {}).get("sponsor", ""),
            "server_location": ", ".join(
                p
                for p in [
                    result.get("server", {}).get("name", ""),
                    result.get("server", {}).get("country", ""),
                ]
                if p
            ),
        }

    return await asyncio.to_thread(_blocking)


class SpeedtestConnector(Connector):
    name = "speedtest"

    def __init__(self, db: Database, interval_minutes: int = 0) -> None:
        self._db = db
        self._interval_minutes = interval_minutes

    async def setup(self) -> None:
        return None

    async def health(self) -> bool:
        # Always healthy — speedtest-cli has no persistent connection.
        return True

    @property
    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="run_speedtest",
                description=(
                    "Run an internet speed test right now. Measures download speed, "
                    "upload speed, and ping latency. Returns results in Mbps."
                ),
                input_schema={"type": "object", "properties": {}},
                execute=self._run_and_store,
                connector_name=self.name,
                long_running=True,
            ),
            Tool(
                name="get_speedtest_history",
                description=(
                    "Get recent internet speed test results. Returns the most recent "
                    "tests with download/upload speeds and ping times."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Number of recent results to return (default 20, max 100)",
                        },
                    },
                },
                execute=self._get_history,
                connector_name=self.name,
            ),
        ]

    async def _store_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """Insert a speed test result into the database and return the full row."""
        row_id = str(ulid.new())
        tested_at = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            """INSERT INTO speedtest_results
               (id, download_mbps, upload_mbps, ping_ms, server_name, server_location, tested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                row_id,
                result["download_mbps"],
                result["upload_mbps"],
                result["ping_ms"],
                result.get("server_name", ""),
                result.get("server_location", ""),
                tested_at,
            ),
        )
        return {**result, "id": row_id, "tested_at": tested_at}

    async def _run_and_store(self) -> dict[str, Any]:
        """Tool handler: run a speed test and persist it."""
        try:
            result = await _run_speedtest()
        except Exception as e:
            logger.exception("Speed test failed")
            return {"error": f"Speed test failed: {e}"}
        if "error" in result:
            return result
        return await self._store_result(result)

    async def _get_history(self, limit: int = 20) -> dict[str, Any]:
        """Tool handler: return recent speed test results."""
        limit = max(1, min(limit, 100))
        rows = await self._db.fetch_all(
            "SELECT * FROM speedtest_results ORDER BY tested_at DESC LIMIT ?",
            (limit,),
        )
        return {"results": rows, "count": len(rows)}

    # -- Poller interface (called by coordinator tick) --

    async def poll(self) -> int:
        """Run a speed test if enough time has elapsed since the last one.

        Returns 1 if a test was run, 0 otherwise.
        """
        if self._interval_minutes <= 0:
            return 0

        last = await self._db.fetch_one(
            "SELECT tested_at FROM speedtest_results ORDER BY tested_at DESC LIMIT 1"
        )
        if last is not None:
            last_dt = datetime.fromisoformat(last["tested_at"])
            elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if elapsed < self._interval_minutes * 60:
                return 0

        logger.info("Running periodic speed test")
        try:
            result = await _run_speedtest()
            if "error" in result:
                logger.warning("Periodic speed test returned error: %s", result["error"])
                return 0
            stored = await self._store_result(result)
            logger.info(
                "Speed test: %.1f Mbps down / %.1f Mbps up / %.0f ms ping",
                stored["download_mbps"],
                stored["upload_mbps"],
                stored["ping_ms"],
            )
            return 1
        except Exception:
            logger.exception("Periodic speed test failed")
            return 0
