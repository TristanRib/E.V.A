"""Plugin Philips Hue : pilotage des lumières via le bridge local."""

from collections.abc import Sequence
from contextlib import AsyncExitStack
from typing import Any

from eva.domain import Tool
from eva.plugins.base import PluginUnavailable
from eva.plugins.hue.client import HueClient, HueError
from eva.plugins.hue.home import load_home
from eva.plugins.hue.settings import HueSettings
from eva.plugins.hue.tools import create_hue_tools


class HuePlugin:
    name = "hue"

    async def create_tools(self, resources: AsyncExitStack) -> Sequence[Tool[Any]]:
        settings = HueSettings()
        if not (settings.bridge_ip and settings.app_key):
            raise PluginUnavailable("bridge non appairé (lancez `uv run eva-hue-pair`)")

        client = HueClient(settings.bridge_ip, settings.app_key.get_secret_value())
        resources.push_async_callback(client.aclose)
        try:
            home = await load_home(client)
        except HueError as e:
            raise PluginUnavailable(str(e)) from e
        return create_hue_tools(client, home)
