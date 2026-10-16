"""Plugins disponibles et chargement isolé.

Ajouter un plugin = créer son paquet dans `plugins/` + l'ajouter à `PLUGINS`.
"""

import logging
from collections.abc import Collection, Iterable
from contextlib import AsyncExitStack
from typing import Any

from eva.domain import Tool
from eva.plugins.base import Plugin, PluginUnavailable
from eva.plugins.clock import ClockPlugin
from eva.plugins.hue import HuePlugin

logger = logging.getLogger(__name__)

PLUGINS: tuple[Plugin, ...] = (ClockPlugin(), HuePlugin())


async def load_plugins(
    plugins: Iterable[Plugin],
    resources: AsyncExitStack,
    *,
    enabled: Collection[str] | None = None,
) -> list[Tool[Any]]:
    """Charge les outils des plugins activés (`enabled=None` : tous).

    Un plugin indisponible ou en échec est ignoré avec un avertissement : il ne doit
    jamais empêcher E.V.A de démarrer.
    """
    tools: list[Tool[Any]] = []
    for plugin in plugins:
        if enabled is not None and plugin.name not in enabled:
            continue
        try:
            tools.extend(await plugin.create_tools(resources))
        except PluginUnavailable as e:
            logger.warning("Plugin « %s » indisponible : %s", plugin.name, e)
        except Exception:
            logger.exception("Échec du chargement du plugin « %s »", plugin.name)
    return tools
