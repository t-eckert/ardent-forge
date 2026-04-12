import pytest
import respx
from httpx import Response

from forge.tools.weather import WEATHER_TOOL_SCHEMA, get_weather


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
