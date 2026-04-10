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
