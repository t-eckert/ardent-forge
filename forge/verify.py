import asyncio
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    success: bool
    output: str
    commands_run: list[str]


def detect_verify_commands(repo_path: str) -> list[str]:
    commands: list[str] = []

    if os.path.exists(os.path.join(repo_path, "Taskfile.yml")) or os.path.exists(
        os.path.join(repo_path, "Taskfile.yaml")
    ):
        if os.path.exists(os.path.join(repo_path, "taskw")):
            commands.append("./taskw test")
        else:
            commands.append("task test")
        return commands

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
        logger.warning(f"No verification commands detected for {repo_path}")
        return VerificationResult(
            success=True, output="No verification commands found", commands_run=[]
        )

    all_output: list[str] = []
    commands_run: list[str] = []
    for cmd in commands:
        logger.info(f"Running: {cmd} in {repo_path}")
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
        if proc.returncode != 0:
            logger.error(f"Verification failed: {cmd}")
            return VerificationResult(
                success=False, output="\n".join(all_output), commands_run=commands_run
            )

    return VerificationResult(
        success=True, output="\n".join(all_output), commands_run=commands_run
    )
