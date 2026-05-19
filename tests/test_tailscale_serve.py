import pytest
from unittest.mock import AsyncMock, patch, call

from forge.tailscale.serve import TailscaleServe
from forge.repos.models import Repo


def _repo(name: str, dev_port: int | None = None) -> Repo:
    return Repo(name=name, path=f"/tmp/{name}", default_branch="main", dev_port=dev_port)


async def test_available_true_when_tailscale_in_path():
    with patch("forge.tailscale.serve.shutil.which", return_value="/usr/bin/tailscale"):
        assert TailscaleServe.available() is True


async def test_available_false_when_missing():
    with patch("forge.tailscale.serve.shutil.which", return_value=None):
        assert TailscaleServe.available() is False


async def test_sync_no_op_when_unavailable():
    ts = TailscaleServe()
    with patch("forge.tailscale.serve.shutil.which", return_value=None), \
         patch.object(ts, "_reset", new=AsyncMock()) as mock_reset:
        await ts.sync([_repo("app", dev_port=5173)])
    mock_reset.assert_not_called()


async def test_sync_with_no_dev_ports_calls_reset_only():
    ts = TailscaleServe()
    with patch("forge.tailscale.serve.shutil.which", return_value="/usr/bin/tailscale"), \
         patch.object(ts, "_reset", new=AsyncMock()) as mock_reset, \
         patch.object(ts, "_add", new=AsyncMock()) as mock_add:
        await ts.sync([_repo("no-port")])
    mock_reset.assert_awaited_once()
    mock_add.assert_not_called()


async def test_sync_adds_entry_for_each_dev_port():
    ts = TailscaleServe()
    repos = [_repo("app-a", dev_port=5173), _repo("app-b", dev_port=3000), _repo("no-port")]
    with patch("forge.tailscale.serve.shutil.which", return_value="/usr/bin/tailscale"), \
         patch.object(ts, "_reset", new=AsyncMock()), \
         patch.object(ts, "_add", new=AsyncMock()) as mock_add:
        await ts.sync(repos)
    ports = {c.args[0] for c in mock_add.call_args_list}
    assert ports == {5173, 3000}


async def test_sync_continues_after_add_failure():
    ts = TailscaleServe()
    repos = [_repo("a", dev_port=5173), _repo("b", dev_port=3000)]
    with patch("forge.tailscale.serve.shutil.which", return_value="/usr/bin/tailscale"), \
         patch.object(ts, "_reset", new=AsyncMock()), \
         patch.object(ts, "_add", new=AsyncMock(side_effect=[RuntimeError("fail"), None])) as mock_add:
        await ts.sync(repos)  # should not raise
    assert mock_add.call_count == 2


async def test_sync_aborts_on_reset_failure():
    ts = TailscaleServe()
    with patch("forge.tailscale.serve.shutil.which", return_value="/usr/bin/tailscale"), \
         patch.object(ts, "_reset", new=AsyncMock(side_effect=RuntimeError("reset failed"))), \
         patch.object(ts, "_add", new=AsyncMock()) as mock_add:
        await ts.sync([_repo("app", dev_port=5173)])  # should not raise
    mock_add.assert_not_called()
