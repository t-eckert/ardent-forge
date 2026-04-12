# Weather Tool — Design Spec

## Goal

Let users ask weather questions in the Ardent Forge chat ("what's the weather like?", "what will it be on Friday?", "weather in San Diego next week?") and get accurate, conversational responses backed by real data from OpenWeather One Call API 3.0.

## Architecture

Claude tool use, called from the existing chat endpoint. The tool talks to The Weather service over localhost — no direct OpenWeather calls from Ardent Forge, no API key in Forge's process.

```
User message
    ↓
forge/api/chat.py
    ↓
Anthropic SDK with tools=[get_weather]
    ↓
Claude decides to call tool → forge/tools/weather.py
    ↓
HTTP call to The Weather service (localhost:8091)
    ├── GET /geocode?q=<city>          (new endpoint)
    └── GET /weather?lat=<x>&lon=<y>   (existing)
    ↓
Tool result → Claude → streamed response
```

## Components

### The Weather service (Go) — new `/geocode` endpoint

Proxies OpenWeather Geocoding API. Returns the single best match.

**Request:** `GET /geocode?q=San Diego`

**Response:**
```json
{
  "name": "San Diego",
  "country": "US",
  "state": "California",
  "lat": 32.7174202,
  "lon": -117.1627728
}
```

**Errors:** 404 if no match. 400 if `q` missing. 502 if upstream fails.

### Ardent Forge — `forge/tools/weather.py`

Single async function that hits The Weather service.

**Tool definition (Claude-facing):**
```python
{
  "name": "get_weather",
  "description": "Get current weather and 8-day forecast for a location. Use when the user asks about weather, temperature, rain, snow, etc. Defaults to Ottawa if no location given.",
  "input_schema": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "City name like 'San Diego' or 'San Diego, California'. Omit for the default location (Ottawa)."
      }
    }
  }
}
```

**Behavior:**
1. If `location` provided → call `/geocode?q=<location>`, get lat/lon
2. Otherwise → use Ottawa default (handled by The Weather service when no lat/lon passed)
3. Call `/weather?lat=&lon=` (or no params for Ottawa)
4. Return condensed JSON: current conditions + 8-day daily forecast, dropping minutely/hourly/alerts

**Returned shape:**
```json
{
  "location": "San Diego, California, US",
  "current": {
    "time": "2026-04-11T20:00:00-07:00",
    "temp_c": 18.2,
    "feels_like_c": 17.5,
    "humidity": 67,
    "wind_kph": 12.4,
    "description": "clear sky"
  },
  "daily": [
    {
      "date": "2026-04-11",
      "min_c": 13.1,
      "max_c": 22.4,
      "precipitation_mm": 0,
      "description": "clear sky"
    },
    ... (7 more days)
  ]
}
```

### Ardent Forge — `forge/api/chat.py` (extended)

The existing `client.messages.stream()` call gets a `tools=[WEATHER_TOOL]` parameter. The streaming loop becomes a multi-turn loop:

1. Stream Claude's response
2. If Claude finishes with `stop_reason == "tool_use"`: extract the tool call, execute it, append the tool_result to messages, stream another response
3. Loop until Claude finishes with `stop_reason == "end_turn"`

The user sees one continuous stream — tool execution happens transparently mid-stream.

## Data flow examples

**"What's the weather like?"**
- Claude calls `get_weather()` with no location
- Tool calls `/weather` with no params (Ottawa default)
- Returns current Ottawa conditions
- Claude responds: "It's currently 8°C and overcast in Ottawa..."

**"What does the weather look like in San Diego next week?"**
- Claude calls `get_weather(location="San Diego")`
- Tool calls `/geocode?q=San Diego` → lat/lon
- Tool calls `/weather?lat=32.71&lon=-117.16` → forecast
- Claude responds with the 8-day forecast for San Diego

**"What about Saturday?" (follow-up)**
- Claude already has the forecast in conversation context
- No new tool call — just responds from prior data

## Error handling

| Failure | Response to Claude | User experience |
|---------|-------------------|-----------------|
| Geocoding 404 | `{"error": "Could not find location 'X'"}` | Claude asks the user to clarify |
| Weather service down | `{"error": "Weather service unavailable"}` | Claude apologizes, suggests retry |
| OpenWeather 5xx | `{"error": "Weather data temporarily unavailable"}` | Claude apologizes |

Errors are returned as `tool_result` content with `is_error=True` so Claude can react naturally rather than crashing the stream.

## Testing

**The Weather service:**
- Unit test the geocoding endpoint with a mocked OpenWeather response
- Test missing query, no results, upstream failure

**Ardent Forge:**
- Unit test `forge/tools/weather.py` with mocked HTTP responses
  - Default location (no geocode call)
  - Named location (geocode + weather)
  - Geocode error
  - Weather error
- Integration test for chat endpoint with mocked Anthropic SDK to verify tool_use loop works end-to-end

## Out of scope

- Hourly forecasts, weather alerts, precipitation minutely (One Call returns these but we strip them)
- Caching (every weather query hits the API; rate limits are 1000/day on the One Call by Call plan)
- Multiple location matches with disambiguation
- Other tools (calendar, finances, etc.) — this spec is just weather, but `forge/tools/` is set up to host more

## Files changed

**the-weather repo:**
- `internal/weather/api.go` — add geocoding API client
- `internal/server/server.go` — add `/geocode` route handler
- `internal/server/server_test.go` — tests

**ardent-forge repo:**
- `forge/tools/__init__.py` — new
- `forge/tools/weather.py` — new
- `forge/api/chat.py` — extend for tool use
- `tests/test_weather_tool.py` — new
- `tests/test_chat.py` — extend for tool flow
