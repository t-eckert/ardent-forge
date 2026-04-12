"""Prompt builder for the research task handler."""


def build_research_prompt(
    title: str,
    description: str,
    retry_context: str | None = None,
) -> str:
    parts = [
        f"# Research Task: {title}",
        f"\n## Description\n{description}",
        "\n## Instructions",
        "- You are working inside an Obsidian vault (the user's personal notebook).",
        "- Read ./CLAUDE.md first for the vault's conventions on Wiki vs Fields vs Log.",
        "- Use WebSearch and WebFetch to gather information from authoritative sources.",
        "- Synthesize findings into a single markdown file.",
        "- Decide the best path: Wiki/ for transferable knowledge, Fields/ for ongoing life areas.",
        "  Never write to People/, Projects/, +Templates/, +Assets/, or any .base file.",
        "- Use [[Wikilinks]] when referencing concepts or people that may already exist in the vault.",
        "- Include specific references (URLs, titles, authors) so the user can dig deeper.",
        "- Do not commit; just write the file.",
    ]
    if retry_context:
        parts.append(f"\n## Previous Attempt\n{retry_context}")
    return "\n".join(parts)
