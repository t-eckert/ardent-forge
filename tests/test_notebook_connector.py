"""NotebookConnector — wraps the vault as a Connector so Forge (chat) and
agents (via connectors=['notebook']) can read/search/write through the
same tool surface.

Tests exercise each tool's happy path + error path, including the
allowlist enforcement on writes and the asyncio.to_thread offloading
for the sync reader/writer primitives.
"""

import shutil
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
