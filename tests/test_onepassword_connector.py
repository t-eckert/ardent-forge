import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from forge.connectors.onepassword import OPConnector


async def test_available_true_when_op_in_path():
    with patch("forge.connectors.onepassword.shutil.which", return_value="/usr/bin/op"):
        assert OPConnector.available() is True


async def test_available_false_when_op_missing():
    with patch("forge.connectors.onepassword.shutil.which", return_value=None):
        assert OPConnector.available() is False


async def test_health_false_when_op_missing():
    c = OPConnector()
    with patch("forge.connectors.onepassword.shutil.which", return_value=None):
        assert await c.health() is False


async def test_health_false_when_token_unset(monkeypatch):
    c = OPConnector()
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    with patch("forge.connectors.onepassword.shutil.which", return_value="/usr/bin/op"):
        assert await c.health() is False


async def test_health_true_when_token_set(monkeypatch):
    c = OPConnector()
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token123")
    with patch("forge.connectors.onepassword.shutil.which", return_value="/usr/bin/op"):
        assert await c.health() is True


async def test_tools_is_empty():
    assert OPConnector().tools == []


async def test_resolve_refs_skips_when_op_unavailable():
    c = OPConnector()
    env = {"DB_URL": "op://Vault/Item/field", "PLAIN": "value"}
    with patch("forge.connectors.onepassword.shutil.which", return_value=None):
        result = await c.resolve_refs(env)
    assert result == env


async def test_resolve_refs_leaves_non_op_values():
    c = OPConnector()
    with patch.object(c, "_read", new=AsyncMock(return_value="secret")), \
         patch("forge.connectors.onepassword.shutil.which", return_value="/usr/bin/op"):
        result = await c.resolve_refs({"PLAIN": "value", "KEY": "op://V/I/f"})
    assert result["PLAIN"] == "value"
    assert result["KEY"] == "secret"


async def test_resolve_refs_respects_allowlist():
    c = OPConnector()
    env = {
        "ALLOWED": "op://Vault/Item/allowed",
        "BLOCKED": "op://Vault/Item/blocked",
    }
    with patch.object(c, "_read", new=AsyncMock(return_value="resolved")), \
         patch("forge.connectors.onepassword.shutil.which", return_value="/usr/bin/op"):
        result = await c.resolve_refs(env, allowed_paths=["op://Vault/Item/allowed"])
    assert result["ALLOWED"] == "resolved"
    assert result["BLOCKED"] == "op://Vault/Item/blocked"


async def test_resolve_refs_none_allowlist_resolves_all():
    c = OPConnector()
    env = {"A": "op://V/I/a", "B": "op://V/I/b"}
    with patch.object(c, "_read", new=AsyncMock(return_value="val")), \
         patch("forge.connectors.onepassword.shutil.which", return_value="/usr/bin/op"):
        result = await c.resolve_refs(env, allowed_paths=None)
    assert result == {"A": "val", "B": "val"}


async def test_resolve_refs_logs_error_on_read_failure():
    c = OPConnector()
    with patch.object(c, "_read", new=AsyncMock(side_effect=RuntimeError("auth error"))), \
         patch("forge.connectors.onepassword.shutil.which", return_value="/usr/bin/op"):
        result = await c.resolve_refs({"KEY": "op://V/I/f"})
    # leaves unresolved rather than raising
    assert result["KEY"] == "op://V/I/f"
