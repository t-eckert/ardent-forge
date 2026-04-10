from forge.config import Settings


def test_default_settings():
    settings = Settings(anthropic_api_key="test-key", github_token="test-token")
    assert settings.db_path == "forge.db"
    assert settings.poll_interval_seconds == 300
    assert settings.max_concurrent_tasks == 2
    assert settings.host == "0.0.0.0"
    assert settings.port == 7030


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("FORGE_DB_PATH", "/tmp/test.db")
    monkeypatch.setenv("FORGE_POLL_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("FORGE_ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("FORGE_GITHUB_TOKEN", "ghp-test")
    settings = Settings()
    assert settings.db_path == "/tmp/test.db"
    assert settings.poll_interval_seconds == 60
    assert settings.anthropic_api_key == "sk-test"
