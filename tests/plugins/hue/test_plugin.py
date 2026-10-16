"""Assemblage du plugin : maisons configurées, clés et pannes isolées."""

from contextlib import AsyncExitStack

import pytest

from eva.config import Secrets
from eva.plugins import PluginContext, PluginUnavailable
from eva.plugins.hue import HuePlugin
from eva.plugins.hue.client import HueTransport
from eva.plugins.hue.config import HomeConfig, HueConfig, key_secret_name
from fakes_hue import FakeTransport, chalet_bridge, main_bridge

MAISON = HomeConfig(name="Maison", bridge_ip="10.0.0.1")
CHALET = HomeConfig(name="Chalet", bridge_ip="10.0.0.2")
KEYS = Secrets({"HUE_KEY_MAISON": "k1", "HUE_KEY_CHALET": "k2"})


def plugin_with(bridges: dict[str, FakeTransport]) -> HuePlugin:
    def factory(bridge_ip: str, key: str) -> HueTransport:
        return bridges[bridge_ip]

    return HuePlugin(transport_factory=factory)


async def setup(plugin: HuePlugin, config: HueConfig, secrets: Secrets = KEYS) -> list[str]:
    async with AsyncExitStack() as resources:
        tools = await plugin.setup(PluginContext(config, secrets, resources))
    return [tool.name for tool in tools]


async def test_all_homes_share_one_tool_set() -> None:
    plugin = plugin_with({"10.0.0.1": main_bridge(), "10.0.0.2": chalet_bridge()})

    names = await setup(plugin, HueConfig(homes=[MAISON, CHALET]))

    assert names == ["hue_status", "hue_set_lights", "hue_activate_scene"]


async def test_unreachable_home_is_skipped(caplog: pytest.LogCaptureFixture) -> None:
    plugin = plugin_with({"10.0.0.1": main_bridge(), "10.0.0.2": FakeTransport({}, down=True)})

    names = await setup(plugin, HueConfig(homes=[MAISON, CHALET]))

    assert names
    assert "Chalet" in caplog.text


async def test_home_without_key_is_skipped(caplog: pytest.LogCaptureFixture) -> None:
    plugin = plugin_with({"10.0.0.1": main_bridge()})

    await setup(plugin, HueConfig(homes=[MAISON, CHALET]), Secrets({"HUE_KEY_MAISON": "k1"}))

    assert "HUE_KEY_CHALET" in caplog.text


async def test_no_reachable_home_makes_plugin_unavailable() -> None:
    plugin = plugin_with({"10.0.0.1": FakeTransport({}, down=True)})

    with pytest.raises(PluginUnavailable):
        await setup(plugin, HueConfig(homes=[MAISON]))


async def test_no_home_configured_makes_plugin_unavailable() -> None:
    with pytest.raises(PluginUnavailable, match="eva-hue-pair"):
        await setup(plugin_with({}), HueConfig())


def test_duplicate_home_names_are_rejected() -> None:
    with pytest.raises(ValueError):
        HueConfig(homes=[MAISON, HomeConfig(name="maison", bridge_ip="10.0.0.9")])


def test_key_secret_name() -> None:
    assert key_secret_name("Chalet d'été") == "HUE_KEY_CHALET_D_ETE"
