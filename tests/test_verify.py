import os
import pytest

from forge.verify import (
    detect_verify_commands,
    run_verification,
    VerificationResult,
    VerificationStatus,
)


def test_detect_python_uv(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
    commands = detect_verify_commands(str(tmp_path))
    assert any("uv run pytest" in cmd for cmd in commands)


def test_detect_python_pip(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask\n")
    commands = detect_verify_commands(str(tmp_path))
    assert any("pytest" in cmd for cmd in commands)


def test_detect_node(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "vitest"}}\n')
    commands = detect_verify_commands(str(tmp_path))
    assert any("npm" in cmd for cmd in commands)


def test_detect_rust(tmp_path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\n')
    commands = detect_verify_commands(str(tmp_path))
    assert any("cargo" in cmd for cmd in commands)


def test_detect_go(tmp_path):
    (tmp_path / "go.mod").write_text("module test\n")
    commands = detect_verify_commands(str(tmp_path))
    assert any("go" in cmd for cmd in commands)


def test_detect_taskfile(tmp_path):
    # detect_verify_commands only emits `task test` when the Taskfile actually
    # defines a `test` task (verify.py:_taskfile_has_test), so the fixture must
    # declare one — mirroring test_detect_node's package.json test script.
    # Exercises the real `task` binary, which the box provides (go-task).
    (tmp_path / "Taskfile.yml").write_text(
        "version: '3'\ntasks:\n  test:\n    cmds:\n      - echo ok\n"
    )
    commands = detect_verify_commands(str(tmp_path))
    assert any("task" in cmd.lower() for cmd in commands)


def test_detect_empty_dir(tmp_path):
    commands = detect_verify_commands(str(tmp_path))
    assert commands == []


def test_verification_result():
    result = VerificationResult(success=True, output="All tests passed", commands_run=["pytest"])
    assert result.success
    assert "passed" in result.output

    failed = VerificationResult(success=False, output="1 failed", commands_run=["pytest"])
    assert not failed.success


# --- run_verification status semantics (no silent passes) -------------------
#
# `success` is no longer overloaded: it must reflect an explicit status so the
# delivery gate can distinguish "verified" from "couldn't verify".
#   - no test setup detected      -> NO_TESTS, passes (don't block docs/config)
#   - a command ran and passed    -> PASSED, passes
#   - a command failed (nonzero)  -> FAILED, blocks
#   - tests exist but none ran    -> INCONCLUSIVE, blocks (was a silent pass)


async def test_no_commands_is_no_tests(tmp_path):
    result = await run_verification(str(tmp_path), commands=[])
    assert result.status == VerificationStatus.NO_TESTS
    assert result.success is True


async def test_passing_command_is_passed(tmp_path):
    result = await run_verification(str(tmp_path), commands=["true"])
    assert result.status == VerificationStatus.PASSED
    assert result.success is True


async def test_failing_command_is_failed(tmp_path):
    result = await run_verification(str(tmp_path), commands=["false"])
    assert result.status == VerificationStatus.FAILED
    assert result.success is False


async def test_all_tools_missing_is_inconclusive(tmp_path):
    # A detected command whose tool isn't installed exits 127. If nothing else
    # runs, verification couldn't actually happen — must NOT silently pass.
    result = await run_verification(
        str(tmp_path), commands=["forge-no-such-tool-zzz --version"]
    )
    assert result.status == VerificationStatus.INCONCLUSIVE
    assert result.success is False


async def test_missing_tool_plus_passing_command_is_passed(tmp_path):
    # If at least one command actually ran and passed, verification happened.
    result = await run_verification(
        str(tmp_path), commands=["forge-no-such-tool-zzz", "true"]
    )
    assert result.status == VerificationStatus.PASSED
    assert result.success is True
