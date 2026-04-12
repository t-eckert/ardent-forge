# Weather Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a weather tool to Ardent Forge's chat so users can ask "what's the weather?", "what about Friday?", or "weather in San Diego next week?" — backed by The Weather service which proxies OpenWeather One Call API 3.0.

**Architecture:** Two-repo change. (1) The Weather service gets a new `/geocode` endpoint that proxies OpenWeather Geocoding. (2) Ardent Forge gets `forge/tools/weather.py` and the chat endpoint is extended to handle Anthropic's tool_use loop. Tool calls geocode first if the user named a place, then fetches current + 8-day forecast.

**Tech Stack:** Go (the-weather), Python 3.13 (ardent-forge), Anthropic SDK tool use, httpx, FastAPI streaming.

**Reference:** See spec at `docs/superpowers/specs/2026-04-11-weather-tool-design.md`.

---

## File Structure

**the-weather repo:**
```
the-weather/
├── internal/weather/
│   ├── api.go              # MODIFY — add geocoding URL builder
│   └── client.go           # MODIFY — add Geocode() method
├── web/
│   ├── server.go           # MODIFY — add /geocode handler
│   └── server_test.go      # MODIFY — add geocode tests
└── (existing files)
```

**ardent-forge repo:**
```
ardent-forge/
├── forge/
│   ├── tools/
│   │   ├── __init__.py     # NEW — tool registry placeholder
│   │   └── weather.py      # NEW — weather tool implementation
│   └── api/
│       └── chat.py         # MODIFY — add tool_use loop
├── tests/
│   ├── test_weather_tool.py  # NEW — unit tests for the tool
│   └── test_api_chat.py      # MODIFY — add tool_use flow tests
└── (existing files)
```

---

## Phase A: The Weather service — `/geocode` endpoint

### Task 1: Add Geocode method to the weather client

**Repo:** `~/Repos/github.com/t-eckert/the-weather`

**Files:**
- Modify: `internal/weather/api.go`
- Modify: `internal/weather/client.go`
- Modify: `internal/weather/api_test.go`

- [ ] **Step 1: Read existing files to understand the pattern**

```bash
cd ~/Repos/github.com/t-eckert/the-weather
cat internal/weather/api.go
cat internal/weather/client.go
cat internal/weather/api_test.go
```

This shows the existing API URL builder and Client struct so we follow the same pattern.

- [ ] **Step 2: Write a failing test for the geocode URL builder**

Append to `internal/weather/api_test.go`:

```go
func TestGeocodeURL(t *testing.T) {
	url := geocodeAPI("San Diego", "abc123")
	expected := "https://api.openweathermap.org/geo/1.0/direct?q=San+Diego&limit=1&appid=abc123"
	if url != expected {
		t.Fatalf("expected %s, got %s", expected, url)
	}
}
```

- [ ] **Step 3: Run test to verify it fails**

```bash
go test ./internal/weather/ -run TestGeocodeURL
```

Expected: FAIL with "undefined: geocodeAPI"

- [ ] **Step 4: Add the geocodeAPI function in api.go**

In `internal/weather/api.go`, add at the bottom:

```go
import "net/url"

const geocodeURL = "https://api.openweathermap.org/geo/1.0/direct?q=%s&limit=1&appid=%s"

func geocodeAPI(query, apiKey string) string {
	return fmt.Sprintf(geocodeURL, url.QueryEscape(query), apiKey)
}
```

If `net/url` is already imported, skip re-importing. If `fmt` is not imported, add it.

- [ ] **Step 5: Run test to verify it passes**

```bash
go test ./internal/weather/ -run TestGeocodeURL
```

Expected: PASS

- [ ] **Step 6: Write a failing test for Client.Geocode**

Append to `internal/weather/api_test.go`:

```go
func TestGeocodeReturnsFirstResult(t *testing.T) {
	mock := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("q") != "San Diego" {
			t.Fatalf("expected q=San Diego, got %s", r.URL.Query().Get("q"))
		}
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `[{"name":"San Diego","lat":32.7174,"lon":-117.1628,"country":"US","state":"California"}]`)
	}))
	defer mock.Close()

	c := NewClientWithBaseURL("test-key", mock.URL+"/data/3.0/onecall?lat=%s&lon=%s&appid=%s", mock.URL+"/geo/1.0/direct?q=%s&limit=1&appid=%s")
	result, err := c.Geocode(context.Background(), "San Diego")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.Name != "San Diego" || result.Lat != 32.7174 || result.Lon != -117.1628 {
		t.Fatalf("unexpected result: %+v", result)
	}
}

func TestGeocodeNotFound(t *testing.T) {
	mock := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `[]`)
	}))
	defer mock.Close()

	c := NewClientWithBaseURL("test-key", mock.URL+"/data/3.0/onecall?lat=%s&lon=%s&appid=%s", mock.URL+"/geo/1.0/direct?q=%s&limit=1&appid=%s")
	_, err := c.Geocode(context.Background(), "Notarealplace")
	if err != ErrLocationNotFound {
		t.Fatalf("expected ErrLocationNotFound, got %v", err)
	}
}
```

You may need to add imports: `context`, `encoding/json`, `net/http`, `net/http/httptest`, `fmt`.

- [ ] **Step 7: Run tests to verify they fail**

```bash
go test ./internal/weather/ -run TestGeocode
```

Expected: FAIL — Geocode method doesn't exist, NewClientWithBaseURL signature wrong.

- [ ] **Step 8: Update Client to support a geocode base URL and add Geocode method**

In `internal/weather/client.go`, replace the existing Client and constructors with:

```go
package weather

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
)

var ErrLocationNotFound = errors.New("location not found")

type Client struct {
	apiKey         string
	weatherBaseURL string
	geocodeBaseURL string
	httpClient     *http.Client
}

type GeocodeResult struct {
	Name    string  `json:"name"`
	Country string  `json:"country"`
	State   string  `json:"state"`
	Lat     float64 `json:"lat"`
	Lon     float64 `json:"lon"`
}

func NewClient(apiKey string) *Client {
	return &Client{
		apiKey:         apiKey,
		weatherBaseURL: weatherURL,
		geocodeBaseURL: geocodeURL,
		httpClient:     &http.Client{},
	}
}

func NewClientWithBaseURL(apiKey, weatherURLFmt, geocodeURLFmt string) *Client {
	return &Client{
		apiKey:         apiKey,
		weatherBaseURL: weatherURLFmt,
		geocodeBaseURL: geocodeURLFmt,
		httpClient:     &http.Client{},
	}
}

func (c *Client) Geocode(ctx context.Context, query string) (*GeocodeResult, error) {
	url := fmt.Sprintf(c.geocodeBaseURL, queryEscape(query), c.apiKey)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("geocode upstream returned %d: %s", resp.StatusCode, body)
	}
	var results []GeocodeResult
	if err := json.NewDecoder(resp.Body).Decode(&results); err != nil {
		return nil, err
	}
	if len(results) == 0 {
		return nil, ErrLocationNotFound
	}
	return &results[0], nil
}
```

In `internal/weather/api.go`, rename `apiURL` to `weatherURL` if needed for consistency, and add a `queryEscape` helper that uses `net/url`:

```go
package weather

import (
	"fmt"
	"net/url"
)

const weatherURL = "https://api.openweathermap.org/data/3.0/onecall?lat=%s&lon=%s&appid=%s"
const geocodeURL = "https://api.openweathermap.org/geo/1.0/direct?q=%s&limit=1&appid=%s"

func weatherAPI(lat, lon, apiKey string) string {
	return fmt.Sprintf(weatherURL, lat, lon, apiKey)
}

func geocodeAPI(query, apiKey string) string {
	return fmt.Sprintf(geocodeURL, queryEscape(query), apiKey)
}

func queryEscape(s string) string {
	return url.QueryEscape(s)
}
```

If the original function was named `api` and is called from elsewhere, find those references and update them to `weatherAPI` (use `grep -rn "weather.api(" .` to find them).

- [ ] **Step 9: Run all weather tests to verify they pass**

```bash
go test ./internal/weather/ -v
```

Expected: All tests PASS, including new geocode tests.

- [ ] **Step 10: Commit**

```bash
git add internal/weather/
git commit -m "feat: add Geocode method to weather client

Adds OpenWeather Geocoding API support. Returns first match
or ErrLocationNotFound if no results."
```

---

### Task 2: Add `/geocode` HTTP route

**Repo:** `~/Repos/github.com/t-eckert/the-weather`

**Files:**
- Modify: `web/server.go`
- Modify: `web/server_test.go`

- [ ] **Step 1: Read existing server.go to understand the routing pattern**

```bash
cat web/server.go
```

- [ ] **Step 2: Write a failing test for the /geocode endpoint**

Append to `web/server_test.go`:

```go
func TestGeocodeMissingQuery(t *testing.T) {
	cfg := &config.Config{}
	c := newMockGeocodeClient("", nil)
	srv := NewServer(cfg, c)
	req := httptest.NewRequest(http.MethodGet, "/geocode", nil)
	w := httptest.NewRecorder()
	srv.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}

func TestGeocodeReturnsResult(t *testing.T) {
	cfg := &config.Config{}
	c := newMockGeocodeClient(`{"name":"San Diego","country":"US","state":"California","lat":32.7174,"lon":-117.1628}`, nil)
	srv := NewServer(cfg, c)
	req := httptest.NewRequest(http.MethodGet, "/geocode?q=San+Diego", nil)
	w := httptest.NewRecorder()
	srv.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d, body=%s", w.Code, w.Body.String())
	}
	var got map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &got)
	if got["name"] != "San Diego" {
		t.Fatalf("expected name=San Diego, got %v", got["name"])
	}
}

func TestGeocodeNotFound(t *testing.T) {
	cfg := &config.Config{}
	c := newMockGeocodeClient("", weather.ErrLocationNotFound)
	srv := NewServer(cfg, c)
	req := httptest.NewRequest(http.MethodGet, "/geocode?q=Notarealplace", nil)
	w := httptest.NewRecorder()
	srv.ServeHTTP(w, req)
	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}
```

The test references `newMockGeocodeClient` which doesn't exist yet — that's a helper we'll add. The Server may currently take a `*weather.Client` directly; we'll need a small interface to allow mocking. If existing tests already use a similar pattern (e.g. an interface), match that. If they use `*weather.Client` directly, add a new minimal interface.

Add this helper at the top of `web/server_test.go` (after imports):

```go
type mockGeocodeClient struct {
	weatherJSON string
	geocode     *weather.GeocodeResult
	geocodeErr  error
}

func (m *mockGeocodeClient) Get(ctx context.Context, lat, lon string) ([]byte, error) {
	return []byte(m.weatherJSON), nil
}

func (m *mockGeocodeClient) Geocode(ctx context.Context, query string) (*weather.GeocodeResult, error) {
	return m.geocode, m.geocodeErr
}

func newMockGeocodeClient(geocodeJSON string, geocodeErr error) *mockGeocodeClient {
	m := &mockGeocodeClient{geocodeErr: geocodeErr}
	if geocodeJSON != "" {
		var r weather.GeocodeResult
		json.Unmarshal([]byte(geocodeJSON), &r)
		m.geocode = &r
	}
	return m
}
```

The exact `Get` method name should match whatever the Server currently expects from the weather client. Read `web/server.go` to find the actual interface; adapt the mock to match.

- [ ] **Step 3: Run tests to verify they fail**

```bash
go test ./web/ -run TestGeocode
```

Expected: FAIL — `/geocode` route doesn't exist, returns 404 for all routes.

- [ ] **Step 4: Add the /geocode handler in server.go**

Modify `web/server.go`. First, change the Server's client type from `*weather.Client` to a new interface that includes Geocode. Add at the top of the file:

```go
type WeatherClient interface {
	Get(ctx context.Context, lat, lon string) ([]byte, error)
	Geocode(ctx context.Context, query string) (*weather.GeocodeResult, error)
}
```

Match the `Get` method signature to whatever the existing code uses (it might be different — e.g. `Fetch`, or take `cache.Key`). The point is: define the interface to match what server.go actually calls on the client today, plus add Geocode.

Update `NewServer` to take `WeatherClient` instead of `*weather.Client`.

Add a new handler method. In the routing setup (likely a `mux.HandleFunc` call), add:

```go
mux.HandleFunc("/geocode", s.handleGeocode)
```

And add the handler function:

```go
func (s *Server) handleGeocode(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("q")
	if query == "" {
		http.Error(w, `{"error":"missing required query parameter q"}`, http.StatusBadRequest)
		w.Header().Set("Content-Type", "application/json")
		return
	}
	result, err := s.client.Geocode(r.Context(), query)
	if err != nil {
		if errors.Is(err, weather.ErrLocationNotFound) {
			w.Header().Set("Content-Type", "application/json")
			http.Error(w, `{"error":"location not found"}`, http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		http.Error(w, `{"error":"upstream geocoding failed"}`, http.StatusBadGateway)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}
```

Add necessary imports: `errors`, `encoding/json`, `net/http`, and the local `weather` package.

- [ ] **Step 5: Run tests to verify they pass**

```bash
go test ./web/ -v
```

Expected: All tests PASS. If the existing tests broke because the Server now takes an interface, update them to use the same mock helper.

- [ ] **Step 6: Run all tests**

```bash
go test ./...
```

Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add web/
git commit -m "feat: add /geocode endpoint

Proxies OpenWeather Geocoding API. Returns single best match
or 404 if not found."
```

- [ ] **Step 8: Push and rebuild the container**

```bash
git push
```

The Weather is deployed via the container at `ghcr.io/t-eckert/the-weather:latest`. The container needs a fresh build for the new endpoint to be available. Either manually trigger a build, or wait for whatever CI builds the container. After that, on the Bee Link:

```bash
ssh thomaseckert@ardent-forge "sudo systemctl restart the-weather"
```

This will pull the new image because of the `ExecStartPre = podman pull` in the service config.

---

## Phase B: Ardent Forge — weather tool

### Task 3: Tools package scaffold

**Repo:** `~/Repos/github.com/t-eckert/ardent-forge`

**Files:**
- Create: `forge/tools/__init__.py`

- [ ] **Step 1: Create empty package init**

```bash
mkdir -p forge/tools
```

Create `forge/tools/__init__.py` with just:

```python
"""Chat-callable tools for Claude tool use."""
```

- [ ] **Step 2: Commit**

```bash
git add forge/tools/__init__.py
git commit -m "feat(tools): scaffold tools package"
```

---

### Task 4: Weather tool — schema and basic call

**Files:**
- Create: `forge/tools/weather.py`
- Create: `tests/test_weather_tool.py`

This task implements the tool's Anthropic-facing schema and the function that calls The Weather service for the default location (no geocoding yet).

- [ ] **Step 1: Write failing test for the tool schema**

Create `tests/test_weather_tool.py`:

```python
from forge.tools.weather import WEATHER_TOOL_SCHEMA


def test_weather_tool_schema_shape():
    assert WEATHER_TOOL_SCHEMA["name"] == "get_weather"
    assert "description" in WEATHER_TOOL_SCHEMA
    assert "input_schema" in WEATHER_TOOL_SCHEMA
    schema = WEATHER_TOOL_SCHEMA["input_schema"]
    assert schema["type"] == "object"
    assert "location" in schema["properties"]
    # location is optional — no "required" entry needed
    assert "required" not in schema or "location" not in schema.get("required", [])
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_weather_tool.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'forge.tools.weather'"

- [ ] **Step 3: Create the tool module with the schema**

Create `forge/tools/weather.py`:

```python
"""Weather tool — calls The Weather service for current + 8-day forecast."""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:8091"

WEATHER_TOOL_SCHEMA = {
    "name": "get_weather",
    "description": (
        "Get current weather and 8-day daily forecast for a location. "
        "Use this when the user asks about weather, temperature, rain, snow, or "
        "any meteorological condition. Defaults to Ottawa if no location is given."
    ),
    "input_schema": {
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
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_weather_tool.py -v
```

Expected: PASS

- [ ] **Step 5: Write failing test for the default-location call**

Append to `tests/test_weather_tool.py`:

```python
import pytest
import respx
from httpx import Response

from forge.tools.weather import get_weather


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
```

The `respx` library mocks httpx requests. Add it as a test dependency:

```bash
uv add --dev respx
```

- [ ] **Step 6: Run test to verify it fails**

```bash
uv run pytest tests/test_weather_tool.py::test_get_weather_default_location -v
```

Expected: FAIL — `get_weather` not defined.

- [ ] **Step 7: Implement get_weather for default location**

Append to `forge/tools/weather.py`:

```python
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


async def get_weather(
    location: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
) -> dict[str, Any]:
    """Get current weather + 8-day forecast.

    If location is None, returns weather for the service's default (Ottawa).
    Otherwise geocodes the location first.
    """
    location_label = "Ottawa, Ontario, CA"
    params: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=10) as client:
        weather_resp = await client.get(f"{base_url}/", params=params)
        weather_resp.raise_for_status()
        data = weather_resp.json()

    return {
        "location": location_label,
        "current": _format_current(data["current"]),
        "daily": [_format_daily(d) for d in data.get("daily", [])],
    }
```

- [ ] **Step 8: Run test to verify it passes**

```bash
uv run pytest tests/test_weather_tool.py::test_get_weather_default_location -v
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add forge/tools/weather.py tests/test_weather_tool.py pyproject.toml uv.lock
git commit -m "feat(tools): add weather tool with default-location support

Calls The Weather service for current + daily forecast. Converts
Kelvin to Celsius and m/s to kph. Schema declared for Anthropic
tool use."
```

---

### Task 5: Weather tool — geocoding for named locations

**Files:**
- Modify: `forge/tools/weather.py`
- Modify: `tests/test_weather_tool.py`

- [ ] **Step 1: Write failing test for named-location call**

Append to `tests/test_weather_tool.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_weather_tool.py -v
```

Expected: FAIL — geocoding logic not implemented; second test gets 404 from upstream but doesn't translate it.

- [ ] **Step 3: Update get_weather to call geocode when location is provided**

Replace the `get_weather` function in `forge/tools/weather.py` with:

```python
async def get_weather(
    location: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
) -> dict[str, Any]:
    """Get current weather + 8-day forecast.

    If location is None, returns weather for the service's default (Ottawa).
    Otherwise geocodes the location first.
    Returns a dict with an "error" key on failure (so it can be returned
    as a tool_result with is_error=True).
    """
    async with httpx.AsyncClient(timeout=10) as client:
        if location:
            geo_resp = await client.get(f"{base_url}/geocode", params={"q": location})
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

        weather_resp = await client.get(f"{base_url}/", params=params)
        if weather_resp.status_code >= 400:
            return {"error": "Weather data temporarily unavailable"}
        data = weather_resp.json()

    return {
        "location": location_label,
        "current": _format_current(data["current"]),
        "daily": [_format_daily(d) for d in data.get("daily", [])],
    }
```

- [ ] **Step 4: Run all tool tests to verify they pass**

```bash
uv run pytest tests/test_weather_tool.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/tools/weather.py tests/test_weather_tool.py
git commit -m "feat(tools): geocode named locations before fetching weather

Returns {error: ...} on geocoding failure so the caller can
surface it as a tool_result with is_error=True."
```

---

## Phase C: Wire the tool into chat

### Task 6: Add tool_use loop to the chat endpoint

**Files:**
- Modify: `forge/api/chat.py`
- Modify: `tests/test_api_chat.py`

This task changes the chat endpoint from a simple stream to a loop that handles tool calls. Tests use a fake Anthropic client to avoid hitting the API.

- [ ] **Step 1: Refactor the chat handler to use a tool-aware loop**

Replace the `generate` function inside `send_message` in `forge/api/chat.py` with a version that uses `client.messages.create()` (non-streaming initially for simplicity — we'll layer streaming on if needed). Actually, keep streaming but loop. Replace the entire `send_message` function:

```python
@router.post("")
async def send_message(req: ChatRequest):
    store = get_store()

    # Save user message
    await store.save_chat_message(role="user", content=req.content)

    if not _anthropic_api_key:
        fallback = "Chat is not configured. Set FORGE_ANTHROPIC_API_KEY to enable."
        await store.save_chat_message(role="assistant", content=fallback)

        async def fallback_stream():
            yield fallback

        return StreamingResponse(fallback_stream(), media_type="text/plain")

    import anthropic

    from forge.tools.weather import WEATHER_TOOL_SCHEMA, get_weather

    client = _anthropic_client_factory(_anthropic_api_key)

    history = await store.list_chat_messages(limit=50)
    messages: list[dict] = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history
        if msg["role"] in ("user", "assistant")
    ]

    async def generate():
        full_response = ""
        try:
            for _ in range(5):  # cap tool-use loops to prevent runaway
                async with client.messages.stream(
                    model=_chat_model,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    messages=messages,
                    tools=[WEATHER_TOOL_SCHEMA],
                ) as stream:
                    async for text in stream.text_stream:
                        full_response += text
                        yield text
                    final_message = await stream.get_final_message()

                if final_message.stop_reason != "tool_use":
                    break

                # Append assistant message with tool use blocks
                messages.append(
                    {"role": "assistant", "content": final_message.content}
                )

                # Execute each tool_use block and build a tool_result message
                tool_results = []
                for block in final_message.content:
                    if block.type != "tool_use":
                        continue
                    if block.name == "get_weather":
                        result = await get_weather(**block.input)
                        is_error = "error" in result
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                            "is_error": is_error,
                        })
                    else:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Unknown tool: {block.name}",
                            "is_error": True,
                        })
                messages.append({"role": "user", "content": tool_results})
        except Exception as e:
            logger.exception("Chat streaming error")
            error_msg = f"\n\n[Error: {e}]"
            full_response += error_msg
            yield error_msg
        finally:
            await store.save_chat_message(role="assistant", content=full_response)

    return StreamingResponse(generate(), media_type="text/plain")
```

Also add this near the top of the file (after the imports):

```python
def _default_anthropic_client(api_key: str):
    import anthropic
    return anthropic.AsyncAnthropic(api_key=api_key)


_anthropic_client_factory = _default_anthropic_client


def set_anthropic_client_factory(factory):
    """For testing — replace the Anthropic client factory."""
    global _anthropic_client_factory
    _anthropic_client_factory = factory
```

- [ ] **Step 2: Write a test for the tool_use flow with a fake client**

Append to `tests/test_api_chat.py`:

```python
from unittest.mock import AsyncMock, MagicMock

import respx
from httpx import Response


class FakeStreamContext:
    """Mimics anthropic's async context manager streaming response."""

    def __init__(self, text_chunks, final_message):
        self._text_chunks = text_chunks
        self._final_message = final_message

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    @property
    async def text_stream(self):
        for chunk in self._text_chunks:
            yield chunk

    def __getattr__(self, name):
        if name == "text_stream":
            async def gen():
                for c in self._text_chunks:
                    yield c
            return gen()
        raise AttributeError(name)

    async def get_final_message(self):
        return self._final_message


def make_text_block(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def make_tool_use_block(tool_id, name, input_):
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = input_
    return block


@respx.mock
async def test_chat_invokes_weather_tool(client):
    # Mock The Weather service
    respx.get("http://127.0.0.1:8091/").mock(
        return_value=Response(
            200,
            json={
                "current": {
                    "dt": 1775963321,
                    "temp": 280.97,
                    "feels_like": 279.5,
                    "humidity": 80,
                    "wind_speed": 3.5,
                    "weather": [{"description": "overcast clouds"}],
                },
                "daily": [],
            },
        )
    )

    # Two-turn fake Anthropic conversation:
    # Turn 1: assistant emits a tool_use block
    # Turn 2: assistant emits final text
    tool_use_msg = MagicMock()
    tool_use_msg.stop_reason = "tool_use"
    tool_use_msg.content = [make_tool_use_block("toolu_1", "get_weather", {})]

    final_msg = MagicMock()
    final_msg.stop_reason = "end_turn"
    final_msg.content = [make_text_block("It's 8°C and overcast in Ottawa.")]

    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.stream = MagicMock(side_effect=[
        FakeStreamContext([], tool_use_msg),
        FakeStreamContext(["It's 8°C and overcast in Ottawa."], final_msg),
    ])

    chat.set_anthropic_client_factory(lambda key: fake_client)
    chat.configure(store=client.app.state.__dict__.get("_store") or chat._store, anthropic_api_key="fake-key")

    resp = await client.post("/api/chat", json={"content": "what's the weather?"})
    assert resp.status_code == 200
    assert "Ottawa" in resp.text or "overcast" in resp.text.lower()
```

The test wiring is awkward because the chat module uses module-level globals. The simplest fix is to expose the store on the test client app:

In the existing `client` fixture in `test_api_chat.py`, the store is configured via `chat.configure(store=store)` — that already sets the module-level `_store`. So `chat._store` is available.

If the `text_stream` access pattern doesn't quite work with the fake, consult the anthropic SDK docs to mirror its actual interface. The key test value is verifying that the weather tool gets called and the final response includes weather data.

- [ ] **Step 3: Run the test to verify it passes**

```bash
uv run pytest tests/test_api_chat.py::test_chat_invokes_weather_tool -v
```

Expected: PASS. If the FakeStreamContext doesn't quite match what the SDK actually exposes, iterate on the mock until it does — the goal is exercising the tool_use loop end-to-end.

- [ ] **Step 4: Run all chat tests to verify nothing broke**

```bash
uv run pytest tests/test_api_chat.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add forge/api/chat.py tests/test_api_chat.py
git commit -m "feat(chat): handle Claude tool_use loop with weather tool

Wires get_weather into the chat endpoint. Loops up to 5 times
to handle multi-turn tool use. Tool errors surface as is_error
tool_results so Claude can respond gracefully."
```

---

### Task 7: Deploy and verify on the Bee Link

**Files:** None (deployment + manual verification)

- [ ] **Step 1: Push and deploy**

```bash
git push
ssh thomaseckert@ardent-forge "/data/ardent-forge/repo/nix/deploy.sh"
```

- [ ] **Step 2: Verify the weather tool works against The Weather service**

SSH in and curl the service directly:

```bash
ssh thomaseckert@ardent-forge "curl -s http://127.0.0.1:8091/ | head -c 200"
```

Expected: JSON starting with `{"lat":...`

```bash
ssh thomaseckert@ardent-forge "curl -s 'http://127.0.0.1:8091/geocode?q=San+Diego'"
```

Expected: `{"name":"San Diego","country":"US","state":"California","lat":32.7...,"lon":-117.1...}`

If the geocode endpoint 404s, the container hasn't been rebuilt — see Task 2 Step 8.

- [ ] **Step 3: Try it in the chat UI**

Open `https://ardent-forge.feist-gondola.ts.net` in your browser. Go to Chat. Send: "What's the weather like?"

Expected: Claude responds with current Ottawa conditions.

Try: "What about San Diego next week?"

Expected: Claude calls the tool with `location="San Diego"` and responds with the forecast.

- [ ] **Step 4: If anything fails, check logs**

```bash
ssh thomaseckert@ardent-forge "journalctl -u ardent-forge --no-pager -n 30"
```

Common issues:
- 401 from Anthropic → API key not loaded
- Connection refused on 8091 → The Weather service not running
- 404 on /geocode → Container hasn't been rebuilt with the new endpoint

---

## Summary

| Task | Repo | What |
|------|------|------|
| 1 | the-weather | Geocode method on weather client |
| 2 | the-weather | `/geocode` HTTP route |
| 3 | ardent-forge | Tools package scaffold |
| 4 | ardent-forge | Weather tool: schema + default location |
| 5 | ardent-forge | Weather tool: geocoding for named locations |
| 6 | ardent-forge | Wire tool_use loop into chat endpoint |
| 7 | both | Deploy and verify end-to-end |
