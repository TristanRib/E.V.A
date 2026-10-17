"""Plugin Philips Hue : assemble bridges, maisons et outils. Aucune logique ici."""

import asyncio
import logging
from collections.abc import Callable, Sequence
from typing import Any

from eva.domain import Tool
from eva.plugins.base import Plugin, PluginContext, PluginUnavailable
from eva.plugins.hue.application import HueHome, HueHomes
from eva.plugins.hue.config import HomeConfig, HueConfig, key_secret_name
from eva.plugins.hue.domain import HueError
from eva.plugins.hue.infrastructure import HttpTransport, HueClient, HueTransport
from eva.plugins.hue.interfaces.tools import create_hue_tools

logger = logging.getLogger(__name__)

type TransportFactory = Callable[[str, str], HueTransport]
"""(IP du bridge, clé) → transport ; remplaçable dans les tests."""


class HuePlugin(Plugin[HueConfig]):
    config_model = HueConfig

    def __init__(self, transport_factory: TransportFactory | None = None) -> None:
        self._transport_factory = transport_factory

    async def setup(self, context: PluginContext[HueConfig]) -> Sequence[Tool[Any]]:
        if not context.config.homes:
            raise PluginUnavailable("aucune maison configurée (lancez `uv run eva-hue-pair`)")

        connections = await asyncio.gather(
            *(self._connect(home, context) for home in context.config.homes)
        )
        homes = [home for home in connections if home is not None]
        if not homes:
            raise PluginUnavailable("aucune maison joignable")
        return create_hue_tools(HueHomes(homes))

    async def _connect(
        self, config: HomeConfig, context: PluginContext[HueConfig]
    ) -> HueHome | None:
        """Connecte une maison ; en cas d'échec, l'ignore sans pénaliser les autres."""
        secret_name = key_secret_name(config.name)
        key = context.secrets.get(secret_name)
        if key is None:
            logger.warning(
                "Maison « %s » ignorée : clé absente (%s dans .env)", config.name, secret_name
            )
            return None

        transport = self._make_transport(config.bridge_ip, key.get_secret_value(), context)
        try:
            return await HueHome.connect(config.name, HueClient(transport))
        except HueError as e:
            logger.warning("Maison « %s » ignorée : %s", config.name, e)
            return None

    def _make_transport(
        self, bridge_ip: str, key: str, context: PluginContext[HueConfig]
    ) -> HueTransport:
        if self._transport_factory is not None:
            return self._transport_factory(bridge_ip, key)
        transport = HttpTransport(bridge_ip, key)
        context.resources.push_async_callback(transport.aclose)
        return transport
