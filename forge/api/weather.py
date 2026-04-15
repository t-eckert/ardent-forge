"""/api/weather — current weather for the Today surface.

Thin wrapper around the WeatherConnector so the frontend can fetch weather
data without going through the chat tool-use loop.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/weather")


def _connectors(request: Request):
    return getattr(request.app.state, "connectors", None)


@router.get("/current")
async def current_weather(request: Request):
    connectors = _connectors(request)
    if connectors is None:
        return {"error": "Connectors not configured"}
    weather = connectors.get("weather")
    if weather is None:
        return {"error": "Weather connector not registered"}
    result = await weather.tools[0].execute()
    if "error" in result:
        return result
    current = result.get("current", {})
    return {
        "location": result.get("location", ""),
        "currentC": current.get("temp_c", 0),
        "summary": current.get("description", ""),
        "daily": result.get("daily", []),
    }
