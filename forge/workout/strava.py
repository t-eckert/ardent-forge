"""Strava API client with refresh-token rotation.

Strava's OAuth refresh tokens rotate on every exchange — the fresh token
returned from ``/oauth/token`` supersedes the one we sent. If we lose that
new value we lose access to the account. ``StravaTokenStore`` persists the
latest access/refresh pair to disk so a restart doesn't burn the credential.

Configuration flow:
  * ``FORGE_STRAVA_CLIENT_ID`` / ``FORGE_STRAVA_CLIENT_SECRET`` identify the
    registered Strava app — these never change.
  * ``FORGE_STRAVA_REFRESH_TOKEN`` seeds the store on first boot if no
    persisted tokens exist. After that, the store is the source of truth
    and the env var is ignored.
  * ``FORGE_STRAVA_TOKEN_PATH`` (default ``/data/ardent-forge/strava/tokens.json``)
    holds the rotating state. Keep it on a persistent volume.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"

# Refresh this many seconds before the access token expires. Strava issues
# ~6-hour tokens so a 60s safety margin is plenty.
_REFRESH_LEEWAY_SECONDS = 60


@dataclass
class StravaTokens:
    access_token: str
    refresh_token: str
    expires_at: int  # unix timestamp

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StravaTokens":
        return cls(
            access_token=str(data["access_token"]),
            refresh_token=str(data["refresh_token"]),
            expires_at=int(data["expires_at"]),
        )


class StravaTokenStore:
    """Persists the latest Strava token pair to disk.

    Thread-safety isn't necessary here — the connector calls ``ensure_fresh()``
    sequentially within a single tool call. If we ever want concurrent workout
    queries we'll need a lock around ``_refresh``.
    """

    def __init__(self, path: Path, *, seed_refresh_token: str | None = None):
        self._path = path
        self._seed = seed_refresh_token

    def load(self) -> StravaTokens | None:
        try:
            raw = self._path.read_text()
        except FileNotFoundError:
            return None
        except OSError as exc:
            logger.warning("Strava token file unreadable at %s: %s", self._path, exc)
            return None
        try:
            return StravaTokens.from_dict(json.loads(raw))
        except (ValueError, KeyError, TypeError):
            logger.exception("Strava token file malformed at %s; ignoring", self._path)
            return None

    def save(self, tokens: StravaTokens) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write via a tmp file so a crash mid-write can't leave the file
        # half-populated and torch the rotating refresh_token.
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(tokens.to_dict(), indent=2))
        tmp.replace(self._path)

    def initial_refresh_token(self) -> str | None:
        """The refresh token to use if nothing has been persisted yet.

        First-boot seed only. Once ``save()`` has been called with a fresh
        exchange, this is no longer consulted.
        """
        return self._seed


class StravaClient:
    """Minimal async Strava client — refreshes tokens on demand, fetches activities.

    The surface is intentionally narrow: list recent activities, get one
    activity by id. Anything else the agent needs should be a separate,
    named method rather than a generic pass-through — easier to reason
    about rate limits that way.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        token_store: StravaTokenStore,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._tokens: StravaTokens | None = token_store.load()
        self._token_store = token_store
        self._http = http_client  # if None, a client is created per request

    def configured(self) -> bool:
        """True if the client has enough credentials to attempt a call.

        We still need a usable refresh token — either already persisted or
        available via the store's initial seed.
        """
        if not (self._client_id and self._client_secret):
            return False
        if self._tokens is not None:
            return True
        return bool(self._token_store.initial_refresh_token())

    async def list_recent_activities(
        self, *, after: int | None = None, per_page: int = 30
    ) -> list["StravaActivity"]:
        """Return Strava activities newer than ``after`` (unix seconds), newest first.

        Strava's ``/athlete/activities`` returns newest-first already; we just
        cap the page size. The caller should use ``after`` rather than paging
        backwards — workouts more than a few weeks old live better in the
        notebook.
        """
        params: dict[str, Any] = {"per_page": max(1, min(per_page, 100))}
        if after is not None:
            params["after"] = int(after)
        data = await self._get_json("/athlete/activities", params=params)
        return [StravaActivity.from_api(item) for item in data]

    async def get_activity(self, activity_id: int) -> "StravaActivity":
        data = await self._get_json(
            f"/activities/{activity_id}", params={"include_all_efforts": "false"}
        )
        return StravaActivity.from_api(data)

    # ─── internals ─────────────────────────────────────────────────────

    async def _get_json(self, path: str, *, params: dict | None = None) -> Any:
        await self._ensure_fresh()
        assert self._tokens is not None  # ensure_fresh guarantees this
        headers = {"Authorization": f"Bearer {self._tokens.access_token}"}
        url = f"{STRAVA_API_BASE}{path}"
        if self._http is not None:
            resp = await self._http.get(url, params=params, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params, headers=headers)
        if resp.status_code == 401:
            # Token might have been invalidated server-side; force one retry
            # after a hard refresh before giving up.
            await self._refresh()
            assert self._tokens is not None
            headers = {"Authorization": f"Bearer {self._tokens.access_token}"}
            if self._http is not None:
                resp = await self._http.get(url, params=params, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def _ensure_fresh(self) -> None:
        if self._tokens is None:
            await self._refresh()
            return
        if self._tokens.expires_at - _REFRESH_LEEWAY_SECONDS <= time.time():
            await self._refresh()

    async def _refresh(self) -> None:
        refresh = (
            self._tokens.refresh_token
            if self._tokens is not None
            else self._token_store.initial_refresh_token()
        )
        if not refresh:
            raise RuntimeError(
                "Strava refresh token missing — set FORGE_STRAVA_REFRESH_TOKEN "
                "to seed, or restore the persisted token file."
            )
        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh,
        }
        if self._http is not None:
            resp = await self._http.post(STRAVA_TOKEN_URL, data=payload)
        else:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(STRAVA_TOKEN_URL, data=payload)
        resp.raise_for_status()
        data = resp.json()
        self._tokens = StravaTokens(
            access_token=str(data["access_token"]),
            refresh_token=str(data["refresh_token"]),
            expires_at=int(data["expires_at"]),
        )
        self._token_store.save(self._tokens)


@dataclass
class StravaActivity:
    """Flattened view of the Strava activity payload we care about."""

    id: int
    name: str
    type: str  # Strava's top-level category: Run, Ride, Workout, etc.
    sport_type: str  # finer-grained: EasyRun, TrailRun, WeightTraining, ...
    start_date: str  # ISO-8601 in UTC
    elapsed_time_seconds: int
    moving_time_seconds: int
    distance_meters: float
    average_heartrate: float | None
    max_heartrate: float | None
    average_speed_mps: float | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "sport_type": self.sport_type,
            "start_date": self.start_date,
            "elapsed_time_seconds": self.elapsed_time_seconds,
            "moving_time_seconds": self.moving_time_seconds,
            "distance_meters": self.distance_meters,
            "average_heartrate": self.average_heartrate,
            "max_heartrate": self.max_heartrate,
            "average_speed_mps": self.average_speed_mps,
        }

    @classmethod
    def from_api(cls, data: dict) -> "StravaActivity":
        return cls(
            id=int(data["id"]),
            name=str(data.get("name", "")),
            type=str(data.get("type", "")),
            sport_type=str(data.get("sport_type", data.get("type", ""))),
            start_date=str(data.get("start_date", "")),
            elapsed_time_seconds=int(data.get("elapsed_time", 0)),
            moving_time_seconds=int(data.get("moving_time", 0)),
            distance_meters=float(data.get("distance", 0.0)),
            average_heartrate=(
                float(data["average_heartrate"]) if data.get("average_heartrate") else None
            ),
            max_heartrate=(
                float(data["max_heartrate"]) if data.get("max_heartrate") else None
            ),
            average_speed_mps=(
                float(data["average_speed"]) if data.get("average_speed") else None
            ),
        )
