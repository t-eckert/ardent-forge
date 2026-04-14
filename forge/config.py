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

    # Repos
    workspace_dir: str = "/var/lib/ardent-forge/repos"

    # Notebook (Obsidian vault)
    notebook_dir: str = "/data/ardent-forge/notebook"

    # Forge memory — markdown store of things Forge learned about the user
    memory_dir: str = "/data/ardent-forge/memory"

    # Self-building loop
    self_repo: str = "t-eckert/ardent-forge"
    self_repo_url: str = "https://github.com/t-eckert/ardent-forge.git"
    planner_claude_model: str = "claude-opus-4-20250514"

    # Observability
    log_level: str = "INFO"
