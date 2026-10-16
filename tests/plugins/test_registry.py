from collections.abc import Sequence
from contextlib import AsyncExitStack
from typing import Any

import pytest

from eva.domain import Tool
from eva.plugins import PLUGINS, PluginUnavailable, load_plugins
from fakes import EchoTool


class StaticPlugin:
    def __init__(self, name: str, outcome: list[Tool[Any]] | Exception) -> None:
        self.name = name
        self._outcome = outcome

    async def create_tools(self, resources: AsyncExitStack) -> Sequence[Tool[Any]]:
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


async def test_failing_plugins_are_skipped_without_stopping_others(
    caplog: pytest.LogCaptureFixture,
) -> None:
    plugins = [
        StaticPlugin("absent", PluginUnavailable("non configuré")),
        StaticPlugin("bogue", RuntimeError("boom")),
        StaticPlugin("ok", [EchoTool()]),
    ]

    async with AsyncExitStack() as resources:
        tools = await load_plugins(plugins, resources)

    assert [t.name for t in tools] == ["echo"]
    assert "absent" in caplog.text
    assert "bogue" in caplog.text


async def test_only_enabled_plugins_are_loaded() -> None:
    plugins = [StaticPlugin("a", [EchoTool()]), StaticPlugin("b", RuntimeError("non chargé"))]

    async with AsyncExitStack() as resources:
        tools = await load_plugins(plugins, resources, enabled={"a"})

    assert [t.name for t in tools] == ["echo"]


def test_plugin_names_are_unique() -> None:
    names = [plugin.name for plugin in PLUGINS]

    assert len(names) == len(set(names))
