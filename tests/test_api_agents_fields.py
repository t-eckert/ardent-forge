"""Tests for the new Phase F endpoints: /api/agents, /api/fields, /api/notebook."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from forge.agents import AgentRegistry
from forge.agents.echo import EchoAgent
from forge.connectors import ConnectorRegistry
from forge.db import Database
from forge.main import create_app
from forge.orchestrator import ForgeOrchestrator


@pytest.fixture
def app_with_registries(db: Database):
    app = create_app(db)
    connectors = ConnectorRegistry()
    agents = AgentRegistry()
    agents.register(EchoAgent())
    app.state.orchestrator = ForgeOrchestrator(connectors=connectors, agents=agents)
    return app


# ─── /api/agents ────────────────────────────────────────────────────────────


def test_agents_roster_lists_registered(app_with_registries):
    client = TestClient(app_with_registries)
    r = client.get("/api/agents")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    echo = rows[0]
    assert echo["task_type"] == "echo"
    assert echo["stages"] == ["execute"]
    assert echo["connectors"] == []


def test_agents_get_known(app_with_registries):
    client = TestClient(app_with_registries)
    r = client.get("/api/agents/echo")
    assert r.status_code == 200
    assert r.json()["name"] == "echo"


def test_agents_get_missing(app_with_registries):
    client = TestClient(app_with_registries)
    assert client.get("/api/agents/nope").status_code == 404


# ─── /api/fields ────────────────────────────────────────────────────────────


def test_fields_with_no_notebook_reader(db: Database):
    app = create_app(db)
    app.state.notebook_reader = None
    client = TestClient(app)
    assert client.get("/api/fields").json() == []


def test_fields_lists_vault_subdirs(tmp_path: Path, db: Database):
    vault = tmp_path / "vault"
    (vault / "Fields" / "Health").mkdir(parents=True)
    (vault / "Fields" / "Health" / "Workouts.md").write_text("# Workouts\n")
    (vault / "Fields" / "Redpanda").mkdir()
    (vault / "Fields" / "Redpanda" / "Core.md").write_text("# Core\n")

    from forge.notebook import NotebookReader

    app = create_app(db)
    app.state.notebook_reader = NotebookReader(vault)

    client = TestClient(app)
    rows = client.get("/api/fields").json()
    slugs = {r["slug"] for r in rows}
    assert slugs == {"health", "redpanda"}
    health = next(r for r in rows if r["slug"] == "health")
    assert health["entries"] == 1


def test_field_detail_by_slug(tmp_path: Path, db: Database):
    vault = tmp_path / "vault"
    (vault / "Fields" / "Art").mkdir(parents=True)
    from forge.notebook import NotebookReader

    app = create_app(db)
    app.state.notebook_reader = NotebookReader(vault)
    client = TestClient(app)

    r = client.get("/api/fields/art")
    assert r.status_code == 200
    assert r.json()["name"] == "Art"

    assert client.get("/api/fields/nope").status_code == 404


# ─── /api/notebook ──────────────────────────────────────────────────────────


def test_notebook_read_list_search(tmp_path: Path, db: Database):
    vault = tmp_path / "vault"
    (vault / "Log").mkdir(parents=True)
    (vault / "Log" / "2026-04-13.md").write_text("# Today\nHello world\n")
    (vault / "Wiki").mkdir()
    (vault / "Wiki" / "Pizza.md").write_text("# Pizza\nHello world again\n")

    from forge.notebook import NotebookReader

    app = create_app(db)
    app.state.notebook_reader = NotebookReader(vault)
    client = TestClient(app)

    # read
    r = client.get("/api/notebook/read", params={"path": "Log/2026-04-13.md"})
    assert r.status_code == 200
    assert "Hello world" in r.json()["body"]

    # list
    r = client.get("/api/notebook/list")
    assert r.status_code == 200
    assert set(r.json()["entries"]) == {"Log", "Wiki"}

    # search
    r = client.get("/api/notebook/search", params={"q": "Hello"})
    assert r.status_code == 200
    paths = {h["path"] for h in r.json()}
    assert "Log/2026-04-13.md" in paths

    # resolve
    r = client.get("/api/notebook/resolve", params={"name": "Pizza"})
    assert r.status_code == 200
    assert r.json()["path"].endswith("Pizza.md")


def test_notebook_read_404(tmp_path: Path, db: Database):
    vault = tmp_path / "vault"
    vault.mkdir()
    from forge.notebook import NotebookReader

    app = create_app(db)
    app.state.notebook_reader = NotebookReader(vault)
    client = TestClient(app)

    assert client.get("/api/notebook/read", params={"path": "missing.md"}).status_code == 404


def test_notebook_unavailable_503(db: Database):
    app = create_app(db)
    app.state.notebook_reader = None
    client = TestClient(app)
    r = client.get("/api/notebook/read", params={"path": "a.md"})
    assert r.status_code == 503
