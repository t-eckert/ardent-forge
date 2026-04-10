import pytest

from forge.guardrails import check_self_modification


def test_allows_normal_repo():
    result = check_self_modification("t-eckert/myapp", ["forge/api/tasks.py"])
    assert result is None


def test_allows_ardent_forge_safe_files():
    result = check_self_modification(
        "t-eckert/ardent-forge", ["forge/handlers/echo.py", "tests/test_echo.py"]
    )
    assert result is None


def test_blocks_nix_modification():
    result = check_self_modification(
        "t-eckert/ardent-forge", ["nix/configuration.nix"]
    )
    assert result is not None
    assert "nix/" in result


def test_blocks_guardrails_modification():
    result = check_self_modification(
        "t-eckert/ardent-forge", ["forge/guardrails.py"]
    )
    assert result is not None
    assert "guardrails" in result


def test_blocks_claude_md_modification():
    result = check_self_modification(
        "t-eckert/ardent-forge", ["CLAUDE.md"]
    )
    assert result is not None
    assert "CLAUDE.md" in result


def test_blocks_mixed_safe_and_unsafe():
    result = check_self_modification(
        "t-eckert/ardent-forge", ["forge/api/tasks.py", "nix/flake.nix"]
    )
    assert result is not None
