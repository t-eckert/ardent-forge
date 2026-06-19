import os
import pytest
import asyncio

from forge.git import GitOps


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary git repo to work with."""
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    cmds = [
        "git init",
        "git config user.email 'test@test.com'",
        "git config user.name 'Test'",
        "echo 'hello' > README.md",
        "git add .",
        "git commit -m 'initial'",
    ]
    for cmd in cmds:
        os.system(f"cd {repo_dir} && {cmd}")
    return str(repo_dir)


@pytest.fixture
def git_ops(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return GitOps(workspace_dir=str(workspace))


async def test_ensure_repo_clones(git_ops, temp_repo):
    repo_path = await git_ops.ensure_repo(temp_repo, "test-owner/test-repo")
    assert os.path.exists(repo_path)
    assert os.path.exists(os.path.join(repo_path, ".git"))


async def test_ensure_repo_idempotent(git_ops, temp_repo):
    path1 = await git_ops.ensure_repo(temp_repo, "test-owner/test-repo")
    path2 = await git_ops.ensure_repo(temp_repo, "test-owner/test-repo")
    assert path1 == path2


async def test_create_worktree(git_ops, temp_repo):
    repo_path = await git_ops.ensure_repo(temp_repo, "test-owner/test-repo")
    worktree_path = await git_ops.create_worktree(repo_path, "test-branch")
    assert os.path.exists(worktree_path)
    assert os.path.exists(os.path.join(worktree_path, "README.md"))


async def test_cleanup_worktree(git_ops, temp_repo):
    repo_path = await git_ops.ensure_repo(temp_repo, "test-owner/test-repo")
    worktree_path = await git_ops.create_worktree(repo_path, "cleanup-branch")
    assert os.path.exists(worktree_path)
    await git_ops.cleanup_worktree(repo_path, worktree_path)
    assert not os.path.exists(worktree_path)


async def test_get_diff(git_ops, temp_repo):
    repo_path = await git_ops.ensure_repo(temp_repo, "test-owner/test-repo")
    worktree_path = await git_ops.create_worktree(repo_path, "diff-branch")
    with open(os.path.join(worktree_path, "new_file.py"), "w") as f:
        f.write("print('hello')\n")
    await _run(f"cd {worktree_path} && git add . && git commit -m 'add file'")
    diff = await git_ops.get_diff(worktree_path, "main")
    assert "new_file.py" in diff


async def _run(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    return stdout.decode()


async def test_get_changed_files_parses_git_output(tmp_path):
    from unittest.mock import AsyncMock
    from forge.git import GitOps

    git = GitOps(str(tmp_path))
    git._run = AsyncMock(return_value="a.py\nb/c.py\n\n")
    result = await git.get_changed_files("/tmp/wt", base_branch="main")
    assert result == ["a.py", "b/c.py"]


async def test_commit_all_stages_and_commits(tmp_path):
    from unittest.mock import AsyncMock, call
    from forge.git import GitOps

    git = GitOps(str(tmp_path))
    git._run = AsyncMock(side_effect=["", "M  some_file.py\n", ""])
    await git.commit_all("/tmp/wt", "plan: add feature")
    assert git._run.call_count == 3
    calls = git._run.call_args_list
    assert calls[0][0][0] == ["git", "add", "-A"]
    assert calls[1][0][0] == ["git", "status", "--porcelain"]
    assert calls[2][0][0] == ["git", "commit", "-m", "plan: add feature"]


async def test_commit_all_raises_when_nothing_staged(tmp_path):
    from unittest.mock import AsyncMock
    from forge.git import GitOps
    import pytest

    git = GitOps(str(tmp_path))
    git._run = AsyncMock(side_effect=["", ""])
    with pytest.raises(RuntimeError, match="nothing staged"):
        await git.commit_all("/tmp/wt", "empty commit")


async def test_get_working_tree_changes_parses_porcelain_output(tmp_path):
    from unittest.mock import AsyncMock
    from forge.git import GitOps

    git = GitOps(str(tmp_path))
    git._run = AsyncMock(return_value=" M file.py\n?? new.py\nR  old.py -> new.py\n")
    result = await git.get_working_tree_changes("/tmp/wt")
    assert result == ["file.py", "new.py", "new.py"]


async def test_get_working_tree_changes_skips_blank_lines(tmp_path):
    from unittest.mock import AsyncMock
    from forge.git import GitOps

    git = GitOps(str(tmp_path))
    git._run = AsyncMock(return_value="\n M a.py\n\n?? b.py\n\n")
    result = await git.get_working_tree_changes("/tmp/wt")
    assert result == ["a.py", "b.py"]


async def test_get_working_tree_changes_uses_git_status_porcelain(tmp_path):
    from unittest.mock import AsyncMock, call
    from forge.git import GitOps

    git = GitOps(str(tmp_path))
    git._run = AsyncMock(return_value="")
    await git.get_working_tree_changes("/tmp/wt")
    git._run.assert_awaited_once_with(["git", "status", "--porcelain"], cwd="/tmp/wt")


from unittest.mock import AsyncMock


async def test_get_existing_pr_url_returns_url():
    git = GitOps("/tmp")
    git._run = AsyncMock(return_value="https://github.com/o/r/pull/7\n")
    url = await git.get_existing_pr_url("/wt")
    assert url == "https://github.com/o/r/pull/7"


async def test_get_existing_pr_url_none_when_no_pr():
    git = GitOps("/tmp")
    git._run = AsyncMock(side_effect=RuntimeError("no pull requests found"))
    url = await git.get_existing_pr_url("/wt")
    assert url is None


async def test_push_branch_pushes_current_branch():
    git = GitOps("/tmp")
    calls = []

    async def fake_run(cmd, cwd=None):
        calls.append(cmd)
        if cmd[:2] == ["git", "rev-parse"]:
            return "forge/abc\n"
        return ""

    git._run = fake_run
    await git.push_branch("/wt")
    assert ["git", "push", "-u", "origin", "forge/abc"] in calls
