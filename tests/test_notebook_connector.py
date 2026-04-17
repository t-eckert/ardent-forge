"""NotebookConnector — wraps the vault as a Connector so Forge (chat) and
agents (via connectors=['notebook']) can read/search/write through the
same tool surface.

Tests exercise each tool's happy path + error path, including the
allowlist enforcement on writes and the asyncio.to_thread offloading
for the sync reader/writer primitives.
"""

import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from forge.connectors.notebook import NotebookConnector


pytestmark = pytest.mark.skipif(
    shutil.which("rg") is None, reason="ripgrep not installed"
)


@pytest.fixture
def notebook(tmp_path: Path) -> Path:
    """A realistic-ish tiny vault under a temp dir."""
    (tmp_path / "Wiki").mkdir()
    (tmp_path / "Fields" / "Health").mkdir(parents=True)
    (tmp_path / "Log").mkdir()
    (tmp_path / "Wiki" / "Svelte 5.md").write_text(
        "# Svelte 5\nRunes replace reactive declarations.\n"
    )
    (tmp_path / "Fields" / "Health" / "Running.md").write_text(
        "# Running\nLogged a long run on 2026-04-10.\n"
    )
    return tmp_path


@pytest.fixture
async def connector(notebook: Path) -> NotebookConnector:
    c = NotebookConnector(notebook)
    await c.setup()
    return c


async def test_connector_exposes_expected_tools(connector: NotebookConnector):
    names = {t.name for t in connector.tools}
    assert names == {
        "notebook_search",
        "notebook_read",
        "notebook_list",
        "notebook_resolve_wikilink",
        "notebook_recent",
        "notebook_log",
        "notebook_draft_log",
        "notebook_week_review",
        "notebook_stalled_work",
        "notebook_summarize_log",
        "notebook_write",
        "notebook_append",
    }
    assert all(t.connector_name == "notebook" for t in connector.tools)


async def test_health_is_true_when_vault_exists(connector: NotebookConnector):
    assert await connector.health() is True


async def test_health_is_false_when_vault_missing(tmp_path: Path):
    missing = tmp_path / "does-not-exist"
    c = NotebookConnector(missing)
    await c.setup()
    assert await c.health() is False


async def test_search_returns_hits_with_paths_and_line_numbers(connector: NotebookConnector):
    result = await connector._search(query="Runes")
    assert result["total"] >= 1
    hit = result["hits"][0]
    assert hit["path"].endswith("Svelte 5.md")
    assert hit["line_number"] >= 1
    assert "Runes" in hit["line"]
    assert result["truncated"] is False


async def test_search_respects_path_prefix(connector: NotebookConnector):
    result = await connector._search(query="long run", path_prefix="Fields")
    assert result["total"] == 1
    assert result["hits"][0]["path"].startswith("Fields/")


async def test_read_returns_content(connector: NotebookConnector):
    result = await connector._read(path="Wiki/Svelte 5.md")
    assert "Runes replace" in result["content"]
    assert result["path"] == "Wiki/Svelte 5.md"


async def test_read_missing_file_is_tool_error(connector: NotebookConnector):
    result = await connector._read(path="Wiki/Nope.md")
    assert "error" in result


async def test_list_returns_sorted_entries(connector: NotebookConnector):
    result = await connector._list(path="Wiki")
    assert result["entries"] == ["Svelte 5.md"]
    assert result["truncated"] is False


async def test_resolve_wikilink_finds_shortest_match(connector: NotebookConnector):
    result = await connector._resolve_wikilink(name="Svelte 5")
    assert result["path"] == "Wiki/Svelte 5.md"


async def test_resolve_wikilink_missing_returns_null_path(connector: NotebookConnector):
    result = await connector._resolve_wikilink(name="Ghost")
    assert result["path"] is None


async def test_write_honours_allowlist(connector: NotebookConnector, notebook: Path):
    result = await connector._write(path="Wiki/NewNote.md", content="Hello.")
    assert result["status"] == "ok"
    assert (notebook / "Wiki" / "NewNote.md").read_text() == "Hello."


async def test_write_outside_allowlist_is_tool_error(connector: NotebookConnector, notebook: Path):
    result = await connector._write(path="Secrets/passwords.md", content="nope")
    assert "error" in result
    assert "allowlist" in result["error"].lower()
    assert not (notebook / "Secrets").exists()


async def test_append_accumulates(connector: NotebookConnector, notebook: Path):
    path = "Log/today.md"
    await connector._append(path=path, content="line 1\n")
    await connector._append(path=path, content="line 2\n")
    assert (notebook / path).read_text() == "line 1\nline 2\n"


async def test_recent_returns_recently_modified(connector: NotebookConnector):
    result = await connector._recent()
    assert "entries" in result
    assert len(result["entries"]) >= 2
    # Entries should have path and modified fields.
    entry = result["entries"][0]
    assert "path" in entry
    assert "modified" in entry


async def test_recent_scoped_to_section(connector: NotebookConnector):
    result = await connector._recent(section="Wiki")
    assert all("Wiki/" in e["path"] for e in result["entries"])


async def test_recent_limits_results(connector: NotebookConnector):
    result = await connector._recent(limit=1)
    assert len(result["entries"]) == 1


async def test_log_reads_by_date(connector: NotebookConnector, notebook: Path):
    (notebook / "Log" / "2026-04-16.md").write_text("# Wednesday\n- [x] Ship it")
    result = await connector._log(date="2026-04-16")
    assert result["date"] == "2026-04-16"
    assert "Ship it" in result["content"]


async def test_log_missing_date_returns_error(connector: NotebookConnector):
    result = await connector._log(date="1999-01-01")
    assert "error" in result


async def test_write_people_accepted(connector: NotebookConnector, notebook: Path):
    (notebook / "People").mkdir(exist_ok=True)
    result = await connector._write(path="People/Alice.md", content="# Alice")
    assert result["status"] == "ok"
    assert (notebook / "People" / "Alice.md").read_text() == "# Alice"


async def test_write_projects_accepted(connector: NotebookConnector, notebook: Path):
    result = await connector._write(path="Projects/Ship.md", content="# Ship")
    assert result["status"] == "ok"
    assert (notebook / "Projects" / "Ship.md").read_text() == "# Ship"


# ─── Draft log tests ─────────────────────────────────────────────────


async def test_draft_log_creates_from_template(connector: NotebookConnector, notebook: Path):
    """Draft log uses the template when available."""
    (notebook / "+Templates").mkdir(exist_ok=True)
    (notebook / "+Templates" / "Daily Note.md").write_text(
        "---\naliases:\n  - \"{{date:D MMMM YYYY}}\"\n---\n"
        "# {{date:ddd D MMMM YYYY}}\n\n## Work\n\n## Personal\n"
    )
    result = await connector._draft_log(date="2026-04-20")
    assert result["status"] == "drafted"
    assert result["path"] == "Log/2026-04-20.md"
    content = (notebook / "Log" / "2026-04-20.md").read_text()
    assert "20 April 2026" in content
    assert "## Work" in content


async def test_draft_log_without_template(connector: NotebookConnector, notebook: Path):
    """Draft log generates a basic structure when no template exists."""
    result = await connector._draft_log(date="2026-04-21")
    assert result["status"] == "drafted"
    content = (notebook / "Log" / "2026-04-21.md").read_text()
    assert "## Work" in content
    assert "## Personal" in content


async def test_draft_log_refuses_if_exists(connector: NotebookConnector, notebook: Path):
    """Draft log won't overwrite an existing log."""
    (notebook / "Log" / "2026-04-22.md").write_text("# Already here")
    result = await connector._draft_log(date="2026-04-22")
    assert "error" in result
    # Original content preserved.
    assert (notebook / "Log" / "2026-04-22.md").read_text() == "# Already here"


async def test_draft_log_carries_forward_deferred(connector: NotebookConnector, notebook: Path):
    """Deferred tasks [>] from yesterday are carried into the new log."""
    (notebook / "Log" / "2026-04-19.md").write_text(
        "# Sat 19 April 2026\n"
        "- [x] Done task\n"
        "- [>] Finish the report\n"
        "- [>] Call the dentist\n"
        "- [ ] Open task\n"
    )
    result = await connector._draft_log(date="2026-04-20")
    assert result["deferred_count"] == 2
    content = (notebook / "Log" / "2026-04-20.md").read_text()
    assert "Finish the report" in content
    assert "Call the dentist" in content
    # Completed and open tasks should NOT be carried.
    assert "Done task" not in content


async def test_draft_log_defaults_to_today(connector: NotebookConnector, notebook: Path):
    """Omitting date defaults to today."""
    today = datetime.now().strftime("%Y-%m-%d")
    result = await connector._draft_log()
    assert result["date"] == today
    assert result["status"] == "drafted"


# ─── Summarize log tests ─────────────────────────────────────────────


async def test_summarize_log_categorizes_tasks(connector: NotebookConnector, notebook: Path):
    (notebook / "Log" / "2026-04-20.md").write_text(
        "# Sun 20 April 2026\n"
        "- [x] Wrote notebook context\n"
        "- [x] Fixed tests\n"
        "- [>] Review PR\n"
        "- [ ] Deploy\n"
        "- [~] Refactor half done\n"
        "- [!] Skipped meeting\n"
    )
    result = await connector._summarize_log(date="2026-04-20")
    assert result["completed"] == ["Wrote notebook context", "Fixed tests"]
    assert result["deferred"] == ["Review PR"]
    assert result["open"] == ["Deploy"]
    assert result["partial"] == ["Refactor half done"]
    assert result["dropped"] == ["Skipped meeting"]
    assert result["total_tasks"] == 6
    assert result["completion_rate"] == "2/6"


async def test_summarize_log_missing_date(connector: NotebookConnector):
    result = await connector._summarize_log(date="1999-01-01")
    assert "error" in result


async def test_summarize_log_empty_log(connector: NotebookConnector, notebook: Path):
    (notebook / "Log" / "2026-04-23.md").write_text("# Notes\n\nJust some thoughts.\n")
    result = await connector._summarize_log(date="2026-04-23")
    assert result["total_tasks"] == 0
    assert result["completion_rate"] == "no tasks"


# ─── Week review tests ───────────────────────────────────────────────


async def test_week_review_aggregates_tasks(connector: NotebookConnector, notebook: Path):
    """Week review reads multiple logs and aggregates task stats."""
    for day_offset, content in [
        (0, "- [x] Task A\n- [>] Task B\n"),
        (1, "- [x] Task C\n- [x] Task D\n- [ ] Task E\n"),
        (2, "- [>] Task B\n- [x] Task F\n"),
    ]:
        day = datetime(2026, 4, 20) - timedelta(days=day_offset)
        (notebook / "Log" / f"{day.strftime('%Y-%m-%d')}.md").write_text(content)

    result = await connector._week_review(end_date="2026-04-20", days=3)
    assert result["logs_found"] == 3
    assert result["tasks"]["completed"] == 4
    assert result["tasks"]["deferred"] == 2


async def test_week_review_extracts_mentions(connector: NotebookConnector, notebook: Path):
    (notebook / "Log" / "2026-04-25.md").write_text(
        "Met with [[Alice]] and [[Bob]]. Also talked to [[Alice]].\n"
    )
    result = await connector._week_review(end_date="2026-04-25", days=1)
    mentions = {m["name"]: m["count"] for m in result["mentions"]}
    assert mentions["Alice"] == 2
    assert mentions["Bob"] == 1


async def test_week_review_handles_missing_logs(connector: NotebookConnector):
    result = await connector._week_review(end_date="1999-01-07", days=7)
    assert result["logs_found"] == 0
    assert result["logs_missing"] == 7


# ─── Stalled work tests ──────────────────────────────────────────────


async def test_stalled_work_detects_rolling_deferrals(connector: NotebookConnector, notebook: Path):
    """Tasks deferred 3+ times should be flagged."""
    today = datetime.now()
    for i in range(5):
        day = today - timedelta(days=i)
        (notebook / "Log" / f"{day.strftime('%Y-%m-%d')}.md").write_text(
            "- [>] Call the dentist\n- [x] Something else\n"
        )
    result = await connector._stalled_work(lookback_days=5)
    assert len(result["rolling_deferrals"]) >= 1
    assert result["rolling_deferrals"][0]["task"] == "Call the dentist"
    assert result["rolling_deferrals"][0]["times_deferred"] == 5


async def test_stalled_work_detects_unmentioned_projects(connector: NotebookConnector, notebook: Path):
    """Projects not mentioned in any recent log should be flagged."""
    today = datetime.now()
    (notebook / "Projects").mkdir(exist_ok=True)
    (notebook / "Projects" / "Ship Feature.md").write_text("# Ship Feature\n")
    (notebook / "Projects" / "Learn Rust.md").write_text("# Learn Rust\n")
    # Only mention one project in today's log.
    (notebook / "Log" / f"{today.strftime('%Y-%m-%d')}.md").write_text(
        "Worked on Ship Feature today.\n"
    )

    result = await connector._stalled_work(lookback_days=1)
    assert "Learn Rust" in result["stalled_projects"]
    assert "Ship Feature" not in result["stalled_projects"]
