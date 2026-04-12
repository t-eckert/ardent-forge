from forge.handlers.research_prompt import build_research_prompt


def test_includes_title_and_description():
    prompt = build_research_prompt(
        title="OpenClaw Use Cases",
        description="Collect blog posts and YouTube summaries.",
    )
    assert "OpenClaw Use Cases" in prompt
    assert "Collect blog posts and YouTube summaries." in prompt


def test_mentions_vault_conventions():
    prompt = build_research_prompt(title="T", description="D")
    assert "CLAUDE.md" in prompt
    assert "Wiki/" in prompt
    assert "Fields/" in prompt


def test_forbids_disallowed_dirs():
    prompt = build_research_prompt(title="T", description="D")
    # At minimum People and +Templates are called out
    assert "People/" in prompt
    assert "+Templates/" in prompt


def test_retry_context_appended_when_provided():
    prompt = build_research_prompt(
        title="T",
        description="D",
        retry_context="Previous attempt timed out after 600s.",
    )
    assert "Previous Attempt" in prompt
    assert "Previous attempt timed out after 600s." in prompt


def test_retry_context_absent_when_none():
    prompt = build_research_prompt(title="T", description="D")
    assert "Previous Attempt" not in prompt
