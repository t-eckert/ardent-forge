"""Turn agent outputs into Forge's first-person narration.

When an agent finishes a task originating from a thread, the coordinator
asks the orchestrator to post a resolution message. This module produces
the prose for that post — in Forge's voice, concise, referencing the agent
and the artifact.

Phase C ships a lightweight deterministic template. Phase D+ will hand
this to Claude for richer prose when the result warrants it.

See docs/superpowers/specs/2026-04-13-forge-orchestrator.md § Turn Types §
Task resolution turn.
"""

from __future__ import annotations

from typing import Any


def narrate_resolution(agent_name: str, task_title: str, result: dict[str, Any]) -> str:
    """Build a one-sentence narration line for a completed task.

    Examples:
      narrate_resolution("code-agent", "Rename tClient", {"pr_url": "https://…", ...})
        → "code-agent finished — rename tClient. PR: https://…"
      narrate_resolution("research-agent", "Study Rust async", {"files": [...]})
        → "research-agent finished — study Rust async. 3 notes written."
    """
    headline = f"{agent_name} finished — {task_title.lower()}."
    bits: list[str] = []
    if "pr_url" in result and result.get("pr_url"):
        bits.append(f"PR: {result['pr_url']}")
    if "issue_count" in result:
        bits.append(f"{result['issue_count']} issues created")
    if "files" in result and isinstance(result.get("files"), list):
        n = len(result["files"])
        if n:
            bits.append(f"{n} notes written")
    if "error" in result and result.get("error"):
        bits.append(f"note: {result['error']}")
    if bits:
        headline += " " + " · ".join(bits)
    return headline


__all__ = ["narrate_resolution"]
