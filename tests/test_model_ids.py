"""Guard against shipping retired Claude model identifiers.

The dated snapshots `claude-sonnet-4-20250514` (Sonnet 4.0) and
`claude-opus-4-20250514` (Opus 4.0) retired on 2026-06-15. They were hardcoded
across the agent/runner/chat layers and silently broke every Code and Plan
task once the snapshots went away (the CLI/API reject them with "the selected
model ... may not exist"). CLI-driven agents now use the deprecation-robust
aliases `sonnet`/`opus`; the chat API path uses the current `claude-sonnet-4-6`.
This test fails if any retired dated ID reappears in the package source.
"""

from pathlib import Path

RETIRED_MODEL_IDS = (
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
)

FORGE_ROOT = Path(__file__).resolve().parent.parent / "forge"


def test_no_retired_model_ids_in_source():
    offenders: list[str] = []
    for py_file in FORGE_ROOT.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for retired in RETIRED_MODEL_IDS:
            if retired in text:
                offenders.append(f"{py_file.relative_to(FORGE_ROOT.parent)}: {retired}")
    assert not offenders, "Retired Claude model IDs found:\n" + "\n".join(offenders)
