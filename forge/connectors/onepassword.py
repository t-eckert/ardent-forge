"""OPConnector — resolves 1Password op:// references at task start.

Not a chat tool (too risky to let agents freely read any vault item).
Used programmatically by CodeAgent before spawning Claude, scoped by the
per-repo allowed_op_paths allowlist from repo.yaml.

Requires: op CLI in PATH, OP_SERVICE_ACCOUNT_TOKEN in environment
(loaded from /etc/ardent-forge/op-token via systemd EnvironmentFile).
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil

from forge.connectors import Tool

logger = logging.getLogger(__name__)


class OPConnector:
    name = "onepassword"

    @staticmethod
    def available() -> bool:
        return shutil.which("op") is not None

    async def setup(self) -> None:
        if not self.available():
            logger.warning("op CLI not found; secret resolution will be skipped")
        elif not os.environ.get("OP_SERVICE_ACCOUNT_TOKEN"):
            logger.warning("OP_SERVICE_ACCOUNT_TOKEN not set; op reads will fail")

    async def health(self) -> bool:
        if not self.available():
            return False
        return bool(os.environ.get("OP_SERVICE_ACCOUNT_TOKEN"))

    @property
    def tools(self) -> list[Tool]:
        return []

    async def resolve_refs(
        self,
        env: dict[str, str],
        allowed_paths: list[str] | None = None,
    ) -> dict[str, str]:
        """Resolve op:// values in env, gated by allowed_paths.

        If allowed_paths is None, all op:// references are resolved.
        If allowed_paths is provided, only references in that list are resolved;
        others are left as-is and logged as warnings.
        """
        if not self.available():
            logger.warning("op CLI not available; skipping secret resolution")
            return env

        result = dict(env)
        for key, value in env.items():
            if not value.startswith("op://"):
                continue
            ref = value.strip()
            if allowed_paths is not None and ref not in allowed_paths:
                logger.warning(
                    "Secret ref %r for var %r not in repo allowed_op_paths; skipping",
                    ref,
                    key,
                )
                continue
            try:
                result[key] = await self._read(ref)
                logger.debug("Resolved %s from 1Password", key)
            except RuntimeError as e:
                logger.error("Failed to resolve %r: %s", ref, e)

        return result

    async def _read(self, ref: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "op",
            "read",
            ref,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"op read failed: {stderr.decode().strip()}")
        return stdout.decode().strip()
