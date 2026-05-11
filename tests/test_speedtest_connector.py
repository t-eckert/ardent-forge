"""Tests for the SpeedtestConnector — DB storage and polling logic.

The actual speedtest-cli call is mocked to avoid real network traffic.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from forge.connectors.speedtest import SpeedtestConnector
from forge.db import Database

FAKE_RESULT = {
    "download_mbps": 94.32,
    "upload_mbps": 18.75,
    "ping_ms": 12.4,
    "server_name": "TestISP",
    "server_location": "Ottawa, Canada",
}


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
def connector(db):
    return SpeedtestConnector(db=db, interval_minutes=60)


# -- Tool: run_speedtest --


@pytest.mark.asyncio
async def test_run_and_store(connector):
    with patch(
        "forge.connectors.speedtest._run_speedtest",
        new_callable=AsyncMock,
        return_value=FAKE_RESULT,
    ):
        result = await connector._run_and_store()

    assert result["download_mbps"] == 94.32
    assert result["upload_mbps"] == 18.75
    assert result["ping_ms"] == 12.4
    assert "id" in result
    assert "tested_at" in result


@pytest.mark.asyncio
async def test_run_and_store_error(connector):
    with patch(
        "forge.connectors.speedtest._run_speedtest",
        new_callable=AsyncMock,
        side_effect=RuntimeError("no internet"),
    ):
        result = await connector._run_and_store()

    assert "error" in result


# -- Tool: get_speedtest_history --


@pytest.mark.asyncio
async def test_get_history_empty(connector):
    result = await connector._get_history()
    assert result["count"] == 0
    assert result["results"] == []


@pytest.mark.asyncio
async def test_get_history_returns_stored(connector):
    with patch(
        "forge.connectors.speedtest._run_speedtest",
        new_callable=AsyncMock,
        return_value=FAKE_RESULT,
    ):
        await connector._run_and_store()
        await connector._run_and_store()

    result = await connector._get_history(limit=10)
    assert result["count"] == 2
    assert result["results"][0]["download_mbps"] == 94.32


@pytest.mark.asyncio
async def test_get_history_respects_limit(connector):
    with patch(
        "forge.connectors.speedtest._run_speedtest",
        new_callable=AsyncMock,
        return_value=FAKE_RESULT,
    ):
        for _ in range(5):
            await connector._run_and_store()

    result = await connector._get_history(limit=3)
    assert result["count"] == 3


# -- Poller --


@pytest.mark.asyncio
async def test_poll_disabled_when_interval_zero(db):
    c = SpeedtestConnector(db=db, interval_minutes=0)
    assert await c.poll() == 0


@pytest.mark.asyncio
async def test_poll_runs_when_no_history(connector):
    with patch(
        "forge.connectors.speedtest._run_speedtest",
        new_callable=AsyncMock,
        return_value=FAKE_RESULT,
    ):
        result = await connector.poll()

    assert result == 1


@pytest.mark.asyncio
async def test_poll_skips_when_recent(connector):
    with patch(
        "forge.connectors.speedtest._run_speedtest",
        new_callable=AsyncMock,
        return_value=FAKE_RESULT,
    ):
        # First poll runs
        assert await connector.poll() == 1
        # Second poll skips — interval hasn't elapsed
        assert await connector.poll() == 0


@pytest.mark.asyncio
async def test_poll_runs_after_interval(connector, db):
    # Insert a result from 2 hours ago (interval is 60 min)
    old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    await db.execute(
        """INSERT INTO speedtest_results
           (id, download_mbps, upload_mbps, ping_ms, server_name, server_location, tested_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("old-id", 50.0, 10.0, 20.0, "OldISP", "Somewhere", old_time),
    )

    with patch(
        "forge.connectors.speedtest._run_speedtest",
        new_callable=AsyncMock,
        return_value=FAKE_RESULT,
    ):
        assert await connector.poll() == 1


# -- Connector protocol --


def test_tools_list(connector):
    tools = connector.tools
    names = [t.name for t in tools]
    assert "run_speedtest" in names
    assert "get_speedtest_history" in names


@pytest.mark.asyncio
async def test_health(connector):
    assert await connector.health() is True
