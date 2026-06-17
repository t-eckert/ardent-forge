import asyncio
import logging
import os
import shutil
import textwrap
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "sonnet"


class ZellijRunner:
    """Runs Claude Code inside a named Zellij session so the user can attach mid-run.

    Falls back to a direct subprocess when zellij is not installed (CI, tests).
    The session is named ``agent-<task-id>``; the user attaches with:
        ssh box -t zellij attach agent-<task-id>
    """

    def __init__(self, model: str = DEFAULT_MODEL, timeout: int = 300):
        self._model = model
        self._timeout = timeout

    @staticmethod
    def available() -> bool:
        return shutil.which("zellij") is not None

    async def run(
        self,
        prompt: str,
        work_dir: str,
        session_name: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> str:
        env = {**os.environ, "CLAUDE_NO_TELEMETRY": "1"}
        if "ANTHROPIC_API_KEY" not in env and "FORGE_ANTHROPIC_API_KEY" in env:
            env["ANTHROPIC_API_KEY"] = env["FORGE_ANTHROPIC_API_KEY"]
        if extra_env:
            env.update(extra_env)
        # Prepend system profile so nix, go, and other host tools are available
        # even when the service PATH is a restricted allowlist.
        system_bins = "/run/current-system/sw/bin:/run/current-system/sw/sbin"
        env["PATH"] = system_bins + ":" + env.get("PATH", "")

        if session_name and self.available():
            logger.info("Running Claude in Zellij session %s (cwd=%s)", session_name, work_dir)
            return await self._run_in_zellij(prompt, work_dir, session_name, env)

        if session_name:
            logger.info("zellij not available; running Claude directly (session=%s)", session_name)
        return await self._run_direct(prompt, work_dir, env)

    async def _run_direct(self, prompt: str, work_dir: str, env: dict) -> str:
        proc = await asyncio.create_subprocess_exec(
            "claude",
            "--print",
            "--dangerously-skip-permissions",
            "--model", self._model,
            "-p", prompt,
            cwd=work_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise TimeoutError(f"Claude Code timed out after {self._timeout}s")
        output = stdout.decode()
        if proc.returncode != 0:
            error = stderr.decode().strip() or output.strip() or "(no output)"
            logger.error("Claude Code failed (rc=%d): %s", proc.returncode, error)
            raise RuntimeError(f"Claude Code failed: {error}")
        return output

    async def _run_in_zellij(
        self, prompt: str, work_dir: str, session_name: str, env: dict
    ) -> str:
        session_dir = Path(f"/tmp/ardent-forge-{session_name}")
        session_dir.mkdir(parents=True, exist_ok=True)

        prompt_file = session_dir / "prompt.txt"
        output_file = session_dir / "output.txt"
        exit_file = session_dir / "exit_code"
        runner_file = session_dir / "runner.py"

        prompt_file.write_text(prompt)

        # Use a Python runner to avoid shell-quoting issues with the prompt
        runner_code = textwrap.dedent(f"""\
            import subprocess, pathlib, os

            prompt = pathlib.Path({str(prompt_file)!r}).read_text()
            env = dict(os.environ)
            forge_key = env.get('FORGE_ANTHROPIC_API_KEY', '')
            if forge_key and 'ANTHROPIC_API_KEY' not in env:
                env['ANTHROPIC_API_KEY'] = forge_key
            env['CLAUDE_NO_TELEMETRY'] = '1'

            result = subprocess.run(
                ['claude', '--print', '--dangerously-skip-permissions',
                 '--model', {self._model!r}, '-p', prompt],
                cwd={work_dir!r},
                capture_output=True,
                text=True,
                env=env,
            )

            out = result.stdout
            if result.returncode != 0:
                out += result.stderr
            pathlib.Path({str(output_file)!r}).write_text(out)
            pathlib.Path({str(exit_file)!r}).write_text(str(result.returncode))
        """)
        runner_file.write_text(runner_code)

        proc = await asyncio.create_subprocess_exec(
            "zellij", "run",
            "--session", session_name,
            "--",
            "python3", str(runner_file),
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()  # zellij run exits immediately after spawning the pane

        deadline = asyncio.get_event_loop().time() + self._timeout
        while asyncio.get_event_loop().time() < deadline:
            if exit_file.exists():
                break
            await asyncio.sleep(3)
        else:
            raise TimeoutError(
                f"Claude Code timed out after {self._timeout}s "
                f"(attach: ssh box -t zellij attach {session_name})"
            )

        rc = int(exit_file.read_text().strip() or "1")
        output = output_file.read_text() if output_file.exists() else ""

        shutil.rmtree(session_dir, ignore_errors=True)

        if rc != 0:
            raise RuntimeError(f"Claude Code failed (rc={rc}): {output[:500]}")
        return output


async def kill_session(session_name: str) -> None:
    """Tear down a Zellij session by name. Tolerant of an already-gone session
    and of zellij not being installed (tests/CI) — never raises."""
    if shutil.which("zellij") is None:
        return
    try:
        proc = await asyncio.create_subprocess_exec(
            "zellij",
            "kill-session",
            session_name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    except Exception:
        logger.warning("Failed to kill zellij session %s", session_name, exc_info=True)
