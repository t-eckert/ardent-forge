from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "FORGE_"}

    # Database
    db_path: str = "forge.db"

    # Coordinator
    poll_interval_seconds: int = 300
    max_concurrent_tasks: int = 2

    # Server
    host: str = "0.0.0.0"
    port: int = 7030

    # API Keys
    anthropic_api_key: str = ""
    github_token: str = ""
    linear_api_key: str = ""
    linear_team_id: str = ""

    # Web search (Tavily)
    tavily_api_key: str = ""

    # Strava — OAuth creds + rotating refresh token state.
    # REFRESH_TOKEN is seed-only: the connector persists the latest token
    # to TOKEN_PATH and uses that as the source of truth afterward.
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_refresh_token: str = ""
    strava_token_path: str = "/data/ardent-forge/strava/tokens.json"

    # Repos — shared with manual checkouts; agent worktrees are sub-dirs
    workspace_dir: str = "/home/thomaseckert/Repos"

    # Notebook (Obsidian vault)
    notebook_dir: str = "/data/ardent-forge/notebook"

    # Art study — syllabus-anchored agent. Phase 1 start is the Monday of
    # week 1; phases 2 and 3 derive from it via default_phase_schedule.
    art_syllabus_path: str = "Artistic Course of Study.md"
    art_phase_1_start: str = "2026-04-13"

    # Forge memory — markdown store of things Forge learned about the user
    memory_dir: str = "/data/ardent-forge/memory"

    # Self-building loop
    self_repo: str = "t-eckert/ardent-forge"
    self_repo_url: str = "https://github.com/t-eckert/ardent-forge.git"
    planner_claude_model: str = "claude-opus-4-20250514"

    # Speed test — periodic internet bandwidth measurement.
    # Set to 0 to disable. Value is in minutes between tests.
    speedtest_interval_minutes: int = 0

    # Observability
    log_level: str = "INFO"
