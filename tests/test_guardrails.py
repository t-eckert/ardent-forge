from forge.guardrails import check_self_modification


def test_allows_normal_repo():
    result = check_self_modification("t-eckert/myapp", ["forge/api/tasks.py"])
    assert result is None


def test_allows_ardent_forge_safe_files():
    result = check_self_modification(
        "t-eckert/ardent-forge", ["forge/handlers/echo.py", "tests/test_echo.py"]
    )
    assert result is None


def test_blocks_nix_modification():
    result = check_self_modification("t-eckert/ardent-forge", ["nix/configuration.nix"])
    assert result is not None
    assert "nix/" in result


def test_blocks_guardrails_modification():
    result = check_self_modification("t-eckert/ardent-forge", ["forge/guardrails.py"])
    assert result is not None
    assert "guardrails" in result


def test_blocks_claude_md_modification():
    result = check_self_modification("t-eckert/ardent-forge", ["CLAUDE.md"])
    assert result is not None
    assert "CLAUDE.md" in result


def test_blocks_mixed_safe_and_unsafe():
    result = check_self_modification(
        "t-eckert/ardent-forge", ["forge/api/tasks.py", "nix/flake.nix"]
    )
    assert result is not None


from forge.guardrails import check_handler_allowlist


def test_plan_handler_allows_plans_and_specs():
    violations = check_handler_allowlist(
        handler="plan",
        repo="t-eckert/ardent-forge",
        changed_files=[
            "docs/superpowers/plans/2026-04-15-foo.md",
            "docs/superpowers/specs/2026-04-15-foo.md",
        ],
    )
    assert violations is None


def test_plan_handler_rejects_code_files():
    violations = check_handler_allowlist(
        handler="plan",
        repo="t-eckert/ardent-forge",
        changed_files=["forge/main.py"],
    )
    assert violations is not None
    assert "forge/main.py" in violations


def test_tickets_handler_allows_specs_only():
    ok = check_handler_allowlist(
        handler="tickets",
        repo="t-eckert/ardent-forge",
        changed_files=["docs/superpowers/specs/2026-04-15-foo.md"],
    )
    assert ok is None
    bad = check_handler_allowlist(
        handler="tickets",
        repo="t-eckert/ardent-forge",
        changed_files=["docs/superpowers/plans/x.md"],
    )
    assert bad is not None


def test_handler_allowlist_bypassed_for_other_repos():
    ok = check_handler_allowlist(
        handler="plan",
        repo="t-eckert/some-other-repo",
        changed_files=["anywhere.py"],
    )
    assert ok is None
