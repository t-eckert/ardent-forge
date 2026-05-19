"""TailscaleServe — manages `tailscale serve` entries for declared dev servers.

Each repo with a dev_port in repo.yaml gets a `tailscale serve --https=<port>`
entry, making it reachable at https://<machine>.<tailnet>:<port>/ from the tailnet
with TLS handled by Tailscale.

sync() is called at startup and whenever the repo registry changes. It resets
the current serve config and re-applies from the registry, so it's idempotent.
"""

from __future__ import annotations

import asyncio
import logging
import shutil

from forge.repos.models import Repo

logger = logging.getLogger(__name__)


class TailscaleServe:
    @staticmethod
    def available() -> bool:
        return shutil.which("tailscale") is not None

    async def sync(self, repos: list[Repo]) -> None:
        """Sync tailscale serve entries to match repos with dev_port declared."""
        if not self.available():
            logger.debug("tailscale CLI not found; skipping serve sync")
            return

        ports = [r.dev_port for r in repos if r.dev_port is not None]

        try:
            await self._reset()
        except RuntimeError as e:
            logger.error("tailscale serve reset failed: %s", e)
            return

        for port in ports:
            try:
                await self._add(port)
                logger.info("tailscale serve: added https=%d → localhost:%d", port, port)
            except RuntimeError as e:
                logger.error("tailscale serve add failed for port %d: %s", port, e)

        if ports:
            logger.info("tailscale serve: synced %d dev server(s)", len(ports))

    async def _reset(self) -> None:
        await self._run(["tailscale", "serve", "reset"])

    async def _add(self, port: int) -> None:
        await self._run([
            "tailscale", "serve",
            f"--https={port}",
            f"http://localhost:{port}",
        ])

    async def _run(self, cmd: list[str]) -> str:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode().strip() or "(no output)")
        return stdout.decode()
