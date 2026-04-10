import asyncio
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"


def build_prompt(
    title: str,
    description: str,
    repo: str,
    analysis: str | None = None,
    retry_context: str | None = None,
) -> str:
    parts = [
        f"# Task: {title}",
        f"\n## Repository: {repo}",
        f"\n## Description\n{description}",
    ]
    if analysis:
        parts.append(f"\n## Codebase Analysis\n{analysis}")
    if retry_context:
        parts.append(f"\n## Previous Attempt Context\n{retry_context}")
    parts.append(
        "\n## Instructions"
        "\n- Read the project's CLAUDE.md if it exists for project-specific guidance"
        "\n- Implement the task as described"
        "\n- Write or update tests as appropriate"
        "\n- Run the project's build and test commands to verify your work"
        "\n- Commit your changes with a clear commit message"
    )
    return "\n".join(parts)


class ClaudeRunner:
    def __init__(self, model: str = DEFAULT_MODEL, timeout: int = 300):
        self._model = model
        self._timeout = timeout

    async def run(self, prompt: str, work_dir: str) -> str:
        logger.info(
            f"Running Claude Code in {work_dir} (model={self._model}, timeout={self._timeout}s)"
        )
        proc = await asyncio.create_subprocess_exec(
            "claude",
            "--print",
            "--dangerously-skip-permissions",
            "--model",
            self._model,
            "-p",
            prompt,
            cwd=work_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "CLAUDE_NO_TELEMETRY": "1"},
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise TimeoutError(f"Claude Code timed out after {self._timeout}s")
        output = stdout.decode()
        if proc.returncode != 0:
            error = stderr.decode()
            logger.error(f"Claude Code failed (rc={proc.returncode}): {error}")
            raise RuntimeError(f"Claude Code failed: {error}")
        return output
