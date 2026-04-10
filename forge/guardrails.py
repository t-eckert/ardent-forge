"""Safety guardrails for self-modification."""

SELF_REPO = "t-eckert/ardent-forge"

PROTECTED_PATHS = [
    "nix/",
    "CLAUDE.md",
    "forge/guardrails.py",
]


def check_self_modification(repo: str, changed_files: list[str]) -> str | None:
    if repo != SELF_REPO:
        return None
    violations = []
    for file_path in changed_files:
        for protected in PROTECTED_PATHS:
            if file_path == protected or file_path.startswith(protected):
                violations.append(file_path)
                break
    if violations:
        files = ", ".join(violations)
        return f"Self-modification guardrail: cannot modify protected files: {files}"
    return None
