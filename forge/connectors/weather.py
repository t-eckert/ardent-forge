"""WeatherConnector — wraps The Weather service as a Connector.

Migrated from forge/tools/weather.py. Behaviour is preserved; only the
surface changes — the get_weather function is now exposed as the
WeatherConnector's only tool.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from forge.connectors import Connector, Tool

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:8091"


def _kelvin_to_celsius(k: float) -> float:
    return round(k - 273.15, 1)


def _format_current(current: dict) -> dict:
    return {
        "time": datetime.fromtimestamp(current["dt"], tz=timezone.utc).isoformat(),
        "temp_c": _kelvin_to_celsius(current["temp"]),
        "feels_like_c": _kelvin_to_celsius(current["feels_like"]),
        "humidity": current.get("humidity"),
        "wind_kph": round(current.get("wind_speed", 0) * 3.6, 1),
        "description": current["weather"][0]["description"] if current.get("weather") else "",
    }


def _format_daily(day: dict) -> dict:
    return {
        "date": datetime.fromtimestamp(day["dt"], tz=timezone.utc).date().isoformat(),
        "min_c": _kelvin_to_celsius(day["temp"]["min"]),
        "max_c": _kelvin_to_celsius(day["temp"]["max"]),
        "precipitation_mm": round(day.get("rain", 0) + day.get("snow", 0), 1),
        "description": day["weather"][0]["description"] if day.get("weather") else "",
    }


class WeatherConnector(Connector):
    name = "weather"

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self._base_url = base_url

    async def setup(self) -> None:
        # The Weather service is local; no auth to validate.
        return None

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/")
                return resp.status_code < 500
        except Exception:
            return False

    @property
    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="get_weather",
                description=(
                    "Get current weather and 8-day daily forecast for a location. "
                    "Use this when the user asks about weather, temperature, rain, snow, "
                    "or any meteorological condition. Defaults to Ottawa if no location is given."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": (
                                "City name, optionally with state/country, e.g. 'San Diego' "
                                "or 'San Diego, California'. Omit for the default location (Ottawa)."
                            ),
                        }
                    },
                },
                execute=self._get_weather,
                connector_name=self.name,
            )
        ]

    async def _get_weather(self, location: str | None = None) -> dict[str, Any]:
        """Get current weather + 8-day forecast.

        If location is None, returns weather for the service's default (Ottawa).
        Otherwise geocodes the location first. Returns a dict with an "error" key on
        failure so the caller can surface it as tool_result with is_error=True.
        """
        async with httpx.AsyncClient(timeout=10) as client:
            if location:
                geo_resp = await client.get(f"{self._base_url}/geocode", params={"q": location})
                if geo_resp.status_code == 404:
                    return {"error": f"Could not find location '{location}'"}
                if geo_resp.status_code >= 400:
                    return {"error": "Geocoding service unavailable"}
                geo = geo_resp.json()
                location_label = ", ".join(
                    p for p in [geo.get("name"), geo.get("state"), geo.get("country")] if p
                )
                params = {"lat": str(geo["lat"]), "lon": str(geo["lon"])}
            else:
                location_label = "Ottawa, Ontario, CA"
                params = {}

            weather_resp = await client.get(f"{self._base_url}/", params=params)
            if weather_resp.status_code >= 400:
                return {"error": "Weather data temporarily unavailable"}
            data = weather_resp.json()

        return {
            "location": location_label,
            "current": _format_current(data["current"]),
            "daily": [_format_daily(d) for d in data.get("daily", [])],
        }
