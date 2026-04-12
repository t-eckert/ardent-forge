"""Safety guardrails for self-modification."""

SELF_REPO = "t-eckert/ardent-forge"

PROTECTED_PATHS = [
    "nix/",
    "CLAUDE.md",
    "forge/guardrails.py",
]

HANDLER_ALLOWLISTS: dict[str, list[str]] = {
    "plan": [
        "docs/superpowers/plans/",
        "docs/superpowers/specs/",
    ],
    "tickets": [
        "docs/superpowers/specs/",
    ],
}


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


def check_handler_allowlist(
    handler: str, repo: str, changed_files: list[str]
) -> str | None:
    """For handlers with a narrow write scope, reject files outside the allowlist.

    Only enforced for the AF self-repo; other repos are unrestricted.
    """
    if repo != SELF_REPO:
        return None
    allowlist = HANDLER_ALLOWLISTS.get(handler)
    if allowlist is None:
        return None
    violations = []
    for file_path in changed_files:
        if not any(file_path.startswith(prefix) for prefix in allowlist):
            violations.append(file_path)
    if violations:
        files = ", ".join(violations)
        return f"Handler '{handler}' allowlist violation: {files}"
    return None
