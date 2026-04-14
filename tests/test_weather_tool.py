import pytest
import respx
from httpx import Response

from forge.connectors.weather import WeatherConnector

_connector = WeatherConnector()
_weather_tool = _connector.tools[0]
WEATHER_TOOL_SCHEMA = _weather_tool.to_anthropic_schema()
get_weather = _weather_tool.execute


def test_weather_tool_schema_shape():
    assert WEATHER_TOOL_SCHEMA["name"] == "get_weather"
    assert "description" in WEATHER_TOOL_SCHEMA
    assert "input_schema" in WEATHER_TOOL_SCHEMA
    schema = WEATHER_TOOL_SCHEMA["input_schema"]
    assert schema["type"] == "object"
    assert "location" in schema["properties"]
    # location is optional — no "required" entry needed
    assert "required" not in schema or "location" not in schema.get("required", [])


@respx.mock
@pytest.mark.asyncio
async def test_get_weather_default_location():
    respx.get("http://127.0.0.1:8091/").mock(
        return_value=Response(
            200,
            json={
                "lat": 45.4215,
                "lon": -75.6972,
                "current": {
                    "dt": 1775963321,
                    "temp": 280.97,
                    "feels_like": 279.5,
                    "humidity": 80,
                    "wind_speed": 3.5,
                    "weather": [{"description": "overcast clouds"}],
                },
                "daily": [
                    {
                        "dt": 1775963321,
                        "temp": {"min": 275.0, "max": 285.0},
                        "weather": [{"description": "overcast clouds"}],
                    }
                ],
            },
        )
    )
    result = await get_weather(location=None)
    assert result["location"] == "Ottawa, Ontario, CA"
    assert "current" in result
    assert result["current"]["temp_c"] == pytest.approx(7.82, rel=0.01)
    assert result["current"]["description"] == "overcast clouds"
    assert len(result["daily"]) == 1


@respx.mock
@pytest.mark.asyncio
async def test_get_weather_named_location():
    respx.get("http://127.0.0.1:8091/geocode", params={"q": "San Diego"}).mock(
        return_value=Response(
            200,
            json={
                "name": "San Diego",
                "country": "US",
                "state": "California",
                "lat": 32.7174,
                "lon": -117.1628,
            },
        )
    )
    respx.get("http://127.0.0.1:8091/", params={"lat": "32.7174", "lon": "-117.1628"}).mock(
        return_value=Response(
            200,
            json={
                "lat": 32.7174,
                "lon": -117.1628,
                "current": {
                    "dt": 1775963321,
                    "temp": 291.4,
                    "feels_like": 290.5,
                    "humidity": 67,
                    "wind_speed": 3.4,
                    "weather": [{"description": "clear sky"}],
                },
                "daily": [],
            },
        )
    )
    result = await get_weather(location="San Diego")
    assert result["location"] == "San Diego, California, US"
    assert result["current"]["temp_c"] == pytest.approx(18.25, rel=0.01)


@respx.mock
@pytest.mark.asyncio
async def test_get_weather_location_not_found():
    respx.get("http://127.0.0.1:8091/geocode", params={"q": "Notarealplace"}).mock(
        return_value=Response(404, json={"error": "location not found"})
    )
    result = await get_weather(location="Notarealplace")
    assert "error" in result
    assert "Notarealplace" in result["error"]
