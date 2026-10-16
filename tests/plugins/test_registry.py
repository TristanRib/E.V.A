import sys
from contextlib import AsyncExitStack
from typing import Any

import pytest

from eva.config import PluginsSettings, Secrets
from eva.domain import Tool
from eva.plugins import PLUGINS, load_plugins
from fakes import EchoTool

FAKES = {
    "ok": "fakes:EchoPlugin",
    "absent": "fakes:UnavailablePlugin",
    "bogue": "fakes:CrashingPlugin",
    "configure": "fakes:ConfiguredPlugin",
    "manquant": "module_inexistant:Plugin",
    "paresseux": "lazy_plugin:LazyPlugin",
}


async def load(settings: PluginsSettings) -> list[Tool[Any]]:
    async with AsyncExitStack() as resources:
        return await load_plugins(settings, Secrets({}), resources, available=FAKES)


async def test_failing_plugins_are_skipped_without_stopping_others(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tools = await load(PluginsSettings(enabled=["absent", "bogue", "manquant", "inconnu", "ok"]))

    assert [t.name for t in tools] == ["echo"]
    for name in ("absent", "bogue", "manquant", "inconnu"):
        assert f"« {name} »" in caplog.text


async def test_disabled_plugin_is_never_imported() -> None:
    await load(PluginsSettings(enabled=["ok"]))

    assert "lazy_plugin" not in sys.modules


async def test_plugin_receives_its_validated_section() -> None:
    settings = PluginsSettings.model_validate({"enabled": ["configure"], "configure": {"value": 7}})

    (tool,) = await load(settings)

    assert tool.name == "echo_7"


async def test_invalid_section_is_reported(caplog: pytest.LogCaptureFixture) -> None:
    settings = PluginsSettings.model_validate(
        {"enabled": ["configure"], "configure": {"value": "abc"}}
    )

    assert await load(settings) == []
    assert "[plugins.configure] invalide" in caplog.text


def test_registered_plugins_point_to_existing_classes() -> None:
    import importlib

    for target in PLUGINS.values():
        module, _, name = target.partition(":")
        assert hasattr(importlib.import_module(module), name), target


def test_fakes_are_usable() -> None:
    assert EchoTool().name == "echo"
