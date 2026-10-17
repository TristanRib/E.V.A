"""Plugins disponibles et chargement isolé.

Ajouter un plugin = créer son paquet dans `plugins/` + l'ajouter à `PLUGINS`.
"""

import importlib
import logging
from collections.abc import Mapping
from contextlib import AsyncExitStack
from typing import Any, cast

from pydantic import ValidationError

from eva.application import ToolRunner
from eva.config import PluginsSettings, Secrets
from eva.domain import Tool
from eva.plugins.base import Plugin, PluginContext, PluginUnavailable

logger = logging.getLogger(__name__)

PLUGINS: Mapping[str, str] = {
    "clock": "eva.plugins.clock:ClockPlugin",
    "hue": "eva.plugins.hue:HuePlugin",
    "routines": "eva.plugins.routines:RoutinesPlugin",
}
"""Nom du plugin → `module:Classe`. L'import n'a lieu qu'au chargement, s'il est activé."""


async def load_plugins(
    settings: PluginsSettings,
    secrets: Secrets,
    resources: AsyncExitStack,
    tools_runner: ToolRunner,
    *,
    available: Mapping[str, str] = PLUGINS,
) -> list[Tool[Any]]:
    """Charge les outils des plugins activés.

    Import, validation de la configuration et préparation sont isolés plugin par plugin :
    un plugin en échec est ignoré avec un avertissement et n'empêche jamais E.V.A de
    démarrer.
    """
    names = settings.enabled if settings.enabled is not None else list(available)
    tools: list[Tool[Any]] = []

    for name in names:
        if name not in available:
            logger.warning(
                "Plugin « %s » inconnu (plugins disponibles : %s)", name, ", ".join(available)
            )
            continue
        try:
            plugin = _instantiate(available[name])
            config = plugin.config_model.model_validate(settings.section(name))
            context = PluginContext(config, secrets, resources, tools_runner)
            tools.extend(await plugin.setup(context))
        except PluginUnavailable as e:
            logger.warning("Plugin « %s » indisponible : %s", name, e)
        except ValidationError as e:
            logger.warning(
                "Plugin « %s » : configuration [plugins.%s] invalide :\n%s", name, name, e
            )
        except Exception:
            logger.exception("Échec du chargement du plugin « %s »", name)
    return tools


def _instantiate(target: str) -> Plugin[Any]:
    module_name, _, class_name = target.partition(":")
    plugin_class = getattr(importlib.import_module(module_name), class_name)
    return cast("Plugin[Any]", plugin_class())
