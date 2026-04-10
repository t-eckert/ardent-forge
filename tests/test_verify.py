import os
import pytest

from forge.verify import detect_verify_commands, VerificationResult


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
    (tmp_path / "Taskfile.yml").write_text("version: '3'\n")
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
