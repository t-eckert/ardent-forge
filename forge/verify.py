import asyncio
import logging
import os
from dataclasses import dataclass
from enum import StrEnum

logger = logging.getLogger(__name__)


class VerificationStatus(StrEnum):
    PASSED = "passed"  # at least one command ran and everything that ran passed
    FAILED = "failed"  # a command exited nonzero — a real verification failure
    NO_TESTS = "no_tests"  # no verification commands detected (nothing to run)
    INCONCLUSIVE = "inconclusive"  # commands detected but none could run (tools missing)


@dataclass
class VerificationResult:
    success: bool
    output: str
    commands_run: list[str]
    status: VerificationStatus = VerificationStatus.PASSED


def _taskfile_has_test(repo_path: str) -> bool:
    """Return True only if a 'test' task is defined in the repo's Taskfile."""
    import subprocess
    try:
        result = subprocess.run(
            ["task", "--list-all"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return any(
            line.strip().startswith("test") or line.strip().startswith("* test")
            for line in result.stdout.splitlines()
        )
    except Exception:
        return False


def detect_verify_commands(repo_path: str) -> list[str]:
    commands: list[str] = []

    if os.path.exists(os.path.join(repo_path, "Taskfile.yml")) or os.path.exists(
        os.path.join(repo_path, "Taskfile.yaml")
    ):
        if _taskfile_has_test(repo_path):
            if os.path.exists(os.path.join(repo_path, "taskw")):
                commands.append("./taskw test")
            else:
                commands.append("task test")
            return commands
        # Taskfile exists but no test task — fall through to other detectors

    if os.path.exists(os.path.join(repo_path, "pyproject.toml")):
        commands.append("uv run pytest -v")
    elif os.path.exists(os.path.join(repo_path, "requirements.txt")):
        commands.append("pytest -v")

    if os.path.exists(os.path.join(repo_path, "package.json")):
        commands.append("npm test")

    if os.path.exists(os.path.join(repo_path, "Cargo.toml")):
        commands.append("cargo check")
        commands.append("cargo test")

    if os.path.exists(os.path.join(repo_path, "go.mod")):
        commands.append("go build ./...")
        commands.append("go test ./...")

    return commands


async def run_verification(
    repo_path: str, commands: list[str] | None = None
) -> VerificationResult:
    if commands is None:
        commands = detect_verify_commands(repo_path)
    if not commands:
        # Nothing to verify — e.g. a docs/config change or a repo with no test
        # setup. We don't block delivery on this, but it is NOT a verified pass;
        # surface NO_TESTS so the caller can record it rather than silently
        # claiming success.
        logger.warning("No verification commands detected for %s", repo_path)
        return VerificationResult(
            success=True,
            output="No verification commands found",
            commands_run=[],
            status=VerificationStatus.NO_TESTS,
        )

    all_output: list[str] = []
    commands_run: list[str] = []
    executed = 0  # commands that actually ran to completion (returncode != 127)
    for cmd in commands:
        logger.info("Running: %s in %s", cmd, repo_path)
        commands_run.append(cmd)
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=repo_path,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode()
        all_output.append(f"$ {cmd}\n{output}")
        if proc.returncode == 127:
            # Command not found — the tool isn't installed in this environment.
            # Skip it, but remember it didn't actually run so we don't mistake a
            # repo full of missing tools for a clean pass.
            logger.warning("Verification tool not found, skipping: %s", cmd)
            continue
        if proc.returncode != 0:
            logger.error("Verification failed: %s", cmd)
            return VerificationResult(
                success=False,
                output="\n".join(all_output),
                commands_run=commands_run,
                status=VerificationStatus.FAILED,
            )
        executed += 1

    if executed == 0:
        # Verification commands were detected (the repo expects to be tested),
        # but none could actually run because their tools are missing. Treat as
        # a gate failure rather than a silent pass — the environment is broken.
        logger.error(
            "Verification inconclusive: %d command(s) detected for %s but none "
            "could run (missing tools)",
            len(commands),
            repo_path,
        )
        return VerificationResult(
            success=False,
            output="\n".join(all_output),
            commands_run=commands_run,
            status=VerificationStatus.INCONCLUSIVE,
        )

    return VerificationResult(
        success=True,
        output="\n".join(all_output),
        commands_run=commands_run,
        status=VerificationStatus.PASSED,
    )
