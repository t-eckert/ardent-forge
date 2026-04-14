"""Unit tests for the Connector + Tool + ConnectorRegistry primitives."""

import pytest

from forge.connectors import Connector, ConnectorRegistry, Tool


class _Fake(Connector):
    """Minimal connector that exposes one or more fake tools."""

    def __init__(self, name: str, tool_names: list[str], healthy: bool = True):
        self.name = name
        self._tool_names = tool_names
        self._healthy = healthy
        self.setup_called = False

    async def setup(self) -> None:
        self.setup_called = True

    async def health(self) -> bool:
        return self._healthy

    @property
    def tools(self) -> list[Tool]:
        return [
            Tool(
                name=n,
                description=f"fake {n}",
                input_schema={"type": "object", "properties": {}},
                execute=self._run,
                connector_name=self.name,
            )
            for n in self._tool_names
        ]

    async def _run(self, **kwargs):
        return {"ok": True, "kwargs": kwargs}


def test_register_and_get():
    reg = ConnectorRegistry()
    c = _Fake("a", ["t1"])
    reg.register(c)
    assert reg.get("a") is c
    assert reg.get("missing") is None


def test_duplicate_registration_raises():
    reg = ConnectorRegistry()
    reg.register(_Fake("a", ["t1"]))
    with pytest.raises(ValueError):
        reg.register(_Fake("a", ["t2"]))


def test_all_tools_spans_connectors():
    reg = ConnectorRegistry()
    reg.register(_Fake("a", ["t1", "t2"]))
    reg.register(_Fake("b", ["t3"]))
    names = {t.name for t in reg.all_tools()}
    assert names == {"t1", "t2", "t3"}


def test_tools_for_scoped():
    reg = ConnectorRegistry()
    reg.register(_Fake("a", ["t1", "t2"]))
    reg.register(_Fake("b", ["t3"]))
    scoped = reg.tools_for(["a"])
    assert {t.name for t in scoped} == {"t1", "t2"}


def test_tools_for_unknown_logs_and_skips(caplog):
    reg = ConnectorRegistry()
    reg.register(_Fake("a", ["t1"]))
    with caplog.at_level("WARNING"):
        scoped = reg.tools_for(["a", "missing"])
    assert {t.name for t in scoped} == {"t1"}
    assert any("missing" in rec.message for rec in caplog.records)


def test_find_tool():
    reg = ConnectorRegistry()
    reg.register(_Fake("a", ["t1"]))
    reg.register(_Fake("b", ["t2"]))
    assert reg.find_tool("t2") is not None
    assert reg.find_tool("t2").connector_name == "b"
    assert reg.find_tool("nope") is None


@pytest.mark.asyncio
async def test_setup_all_calls_each_connector():
    reg = ConnectorRegistry()
    a = _Fake("a", ["t1"])
    b = _Fake("b", ["t2"])
    reg.register(a)
    reg.register(b)
    await reg.setup_all()
    assert a.setup_called and b.setup_called


@pytest.mark.asyncio
async def test_setup_all_swallows_per_connector_failures():
    class _Broken(Connector):
        name = "broken"

        async def setup(self) -> None:
            raise RuntimeError("boom")

        async def health(self) -> bool:
            return False

        @property
        def tools(self) -> list[Tool]:
            return []

    reg = ConnectorRegistry()
    reg.register(_Broken())
    reg.register(_Fake("a", ["t1"]))
    # Should not raise even though _Broken.setup() does.
    await reg.setup_all()


@pytest.mark.asyncio
async def test_health_check_aggregates():
    reg = ConnectorRegistry()
    reg.register(_Fake("a", ["t1"], healthy=True))
    reg.register(_Fake("b", ["t2"], healthy=False))
    h = await reg.health_check()
    assert h == {"a": True, "b": False}


def test_tool_to_anthropic_schema_shape():
    reg = ConnectorRegistry()
    reg.register(_Fake("a", ["t1"]))
    [schema] = [t.to_anthropic_schema() for t in reg.all_tools()]
    assert schema == {
        "name": "t1",
        "description": "fake t1",
        "input_schema": {"type": "object", "properties": {}},
    }
