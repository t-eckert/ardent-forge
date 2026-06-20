import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from forge.zellij.runner import ZellijRunner


async def test_available_returns_false_without_zellij():
    with patch("forge.zellij.runner.shutil.which", return_value=None):
        assert ZellijRunner.available() is False


async def test_available_returns_true_with_zellij():
    with patch("forge.zellij.runner.shutil.which", return_value="/usr/bin/zellij"):
        assert ZellijRunner.available() is True


async def test_run_falls_back_to_direct_when_no_zellij(tmp_path):
    runner = ZellijRunner()
    with patch.object(runner, "_run_direct", new=AsyncMock(return_value="ok")) as mock_direct, \
         patch("forge.zellij.runner.shutil.which", return_value=None):
        result = await runner.run("prompt", str(tmp_path), session_name="agent-test")
    mock_direct.assert_awaited_once()
    assert result == "ok"


async def test_run_uses_direct_when_no_session_name(tmp_path):
    runner = ZellijRunner()
    with patch.object(runner, "_run_direct", new=AsyncMock(return_value="direct")) as mock_direct, \
         patch("forge.zellij.runner.shutil.which", return_value="/usr/bin/zellij"):
        result = await runner.run("prompt", str(tmp_path), session_name=None)
    mock_direct.assert_awaited_once()
    assert result == "direct"


async def test_run_uses_zellij_when_available(tmp_path):
    runner = ZellijRunner()
    with patch.object(runner, "_run_in_zellij", new=AsyncMock(return_value="zellij-out")) as mock_zellij, \
         patch("forge.zellij.runner.shutil.which", return_value="/usr/bin/zellij"):
        result = await runner.run("prompt", str(tmp_path), session_name="agent-abc")
    mock_zellij.assert_awaited_once()
    assert result == "zellij-out"


async def test_run_direct_raises_on_timeout(tmp_path):
    runner = ZellijRunner(timeout=1)
    env = {}
    with patch("forge.zellij.runner.asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_proc.kill = MagicMock()
        mock_proc.communicate = AsyncMock(side_effect=[asyncio.TimeoutError(), (b"", b"")])
        mock_exec.return_value = mock_proc
        with pytest.raises(TimeoutError, match="timed out"):
            await runner._run_direct("prompt", str(tmp_path), env)


async def test_run_direct_raises_on_nonzero_exit(tmp_path):
    runner = ZellijRunner()
    env = {}
    with patch("forge.zellij.runner.asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"some error"))
        mock_exec.return_value = mock_proc
        with pytest.raises(RuntimeError, match="Claude Code failed"):
            await runner._run_direct("prompt", str(tmp_path), env)


async def test_layout_files_exist():
    from forge.zellij.runner import Path as _Path
    import forge.zellij.runner as zmod
    layouts_dir = Path(zmod.__file__).parent / "layouts"
    assert (layouts_dir / "manual.kdl").exists()
    assert (layouts_dir / "agent.kdl").exists()


async def test_kill_session_noop_when_zellij_missing(monkeypatch):
    import forge.zellij.runner as runner

    # Simulate zellij not installed — must be a silent no-op, not an error.
    monkeypatch.setattr(runner.shutil, "which", lambda _: None)
    await runner.kill_session("agent-doesnotexist")  # should not raise


async def test_kill_session_invokes_zellij(monkeypatch):
    import forge.zellij.runner as runner

    calls = []

    class FakeProc:
        async def wait(self):
            return 0

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        return FakeProc()

    monkeypatch.setattr(runner.shutil, "which", lambda _: "/usr/bin/zellij")
    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", fake_exec)

    await runner.kill_session("agent-123")
    assert calls and calls[0][:3] == ("zellij", "kill-session", "agent-123")


async def test_continue_session_adds_continue_flag(monkeypatch):
    captured = {}

    class FakeProc:
        returncode = 0

        async def communicate(self):
            return (b"ok", b"")

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        return FakeProc()

    # Force the direct path (no zellij) and capture the claude argv.
    monkeypatch.setattr(ZellijRunner, "available", staticmethod(lambda: False))
    with patch("forge.zellij.runner.asyncio.create_subprocess_exec", side_effect=fake_exec):
        runner = ZellijRunner(model="sonnet", timeout=5)
        await runner.run("hi", "/tmp", session_name="agent-x", continue_session=True)

    args = list(captured["args"])
    assert "--continue" in args
    # claude requires flags before the -p prompt argument.
    assert args.index("--continue") < args.index("-p")


async def test_no_continue_flag_by_default(monkeypatch):
    captured = {}

    class FakeProc:
        returncode = 0

        async def communicate(self):
            return (b"ok", b"")

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        return FakeProc()

    monkeypatch.setattr(ZellijRunner, "available", staticmethod(lambda: False))
    with patch("forge.zellij.runner.asyncio.create_subprocess_exec", side_effect=fake_exec):
        runner = ZellijRunner(model="sonnet", timeout=5)
        await runner.run("hi", "/tmp", session_name="agent-x")

    assert "--continue" not in captured["args"]
