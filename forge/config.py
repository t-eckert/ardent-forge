from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "FORGE_"}

    # Database
    db_path: str = "forge.db"

    # Coordinator
    poll_interval_seconds: int = 300
    max_concurrent_tasks: int = 2

    # Task resilience — retries with exponential backoff + execution timeout
    max_retries: int = 3
    retry_base_seconds: int = 60
    retry_max_seconds: int = 900
    default_timeout_seconds: int = 1800
    worktree_ttl_hours: int = 48

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

    # Repos — shared with manual checkouts; agent worktrees are sub-dirs
    workspace_dir: str = "/home/thomaseckert/Repos"

    # Projects — collections of related repos grouped under a project name
    projects_dir: str = "/home/thomaseckert/Projects"

    # Notebook (Obsidian vault)
    notebook_dir: str = "/data/ardent-forge/notebook"

    # Forge memory — markdown store of things Forge learned about the user
    memory_dir: str = "/data/ardent-forge/memory"

    # Screenshot uploads — timestamped files; cleaned up after 7 days
    upload_dir: str = "~/tmp/uploads"

    # Self-building loop
    self_repo: str = "t-eckert/ardent-forge"
    self_repo_url: str = "https://github.com/t-eckert/ardent-forge.git"
    planner_claude_model: str = "opus"

    # Speed test — periodic internet bandwidth measurement.
    # Set to 0 to disable. Value is in minutes between tests.
    speedtest_interval_minutes: int = 0

    # Observability
    log_level: str = "INFO"
