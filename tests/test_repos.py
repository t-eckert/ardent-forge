import os
import pytest
from pathlib import Path

from forge.repos.models import Repo, RepoConfig
from forge.repos.registry import RepoRegistry


@pytest.fixture
def workspace(tmp_path):
    return tmp_path / "Repos"


@pytest.fixture
def repo_in_workspace(workspace):
    workspace.mkdir()
    repo = workspace / "my-project"
    repo.mkdir()
    git_dir = repo / ".git"
    git_dir.mkdir()
    # Minimal git config so symbolic-ref doesn't crash
    (git_dir / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
    return repo


async def test_scan_empty_workspace(workspace):
    workspace.mkdir()
    registry = RepoRegistry(str(workspace))
    repos = await registry.scan()
    assert repos == []


async def test_scan_missing_workspace(tmp_path):
    registry = RepoRegistry(str(tmp_path / "nonexistent"))
    repos = await registry.scan()
    assert repos == []


async def test_scan_finds_git_repos(repo_in_workspace, workspace):
    registry = RepoRegistry(str(workspace))
    repos = await registry.scan()
    assert len(repos) == 1
    assert repos[0].name == "my-project"
    assert repos[0].path == str(workspace / "my-project")


async def test_scan_skips_non_git_dirs(workspace):
    workspace.mkdir()
    (workspace / "not-a-repo").mkdir()
    registry = RepoRegistry(str(workspace))
    repos = await registry.scan()
    assert repos == []


async def test_get_returns_repo_after_scan(repo_in_workspace, workspace):
    registry = RepoRegistry(str(workspace))
    await registry.scan()
    repo = registry.get("my-project")
    assert repo is not None
    assert repo.name == "my-project"


async def test_get_returns_none_for_unknown(workspace):
    workspace.mkdir()
    registry = RepoRegistry(str(workspace))
    await registry.scan()
    assert registry.get("does-not-exist") is None


async def test_list_returns_all_scanned(workspace):
    workspace.mkdir()
    for name in ["alpha", "beta", "gamma"]:
        repo = workspace / name
        repo.mkdir()
        (repo / ".git").mkdir()
    registry = RepoRegistry(str(workspace))
    await registry.scan()
    names = {r.name for r in registry.list()}
    assert names == {"alpha", "beta", "gamma"}


def test_repo_config_defaults():
    config = RepoConfig()
    assert config.dev_port is None
    assert config.allowed_op_paths == []


def test_repo_config_with_dev_port():
    config = RepoConfig(dev_port=5173)
    assert config.dev_port == 5173


async def test_repo_yaml_is_parsed(workspace):
    workspace.mkdir()
    repo = workspace / "web-app"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "repo.yaml").write_text("dev_port: 5173\nclaude_label: claude\n")
    registry = RepoRegistry(str(workspace))
    await registry.scan()
    r = registry.get("web-app")
    assert r is not None
    assert r.dev_port == 5173


async def test_invalid_repo_yaml_is_skipped(workspace):
    workspace.mkdir()
    repo = workspace / "broken"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "repo.yaml").write_text(": invalid: yaml: [\n")
    registry = RepoRegistry(str(workspace))
    repos = await registry.scan()
    # Repo still loads, just without config
    assert len(repos) == 1
    assert repos[0].dev_port is None


async def test_config_returns_default_for_unknown_repo(workspace):
    workspace.mkdir()
    registry = RepoRegistry(str(workspace))
    config = registry.config("nonexistent")
    assert isinstance(config, RepoConfig)
    assert config.dev_port is None
