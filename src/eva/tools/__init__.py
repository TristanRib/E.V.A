"""Outils exposés au LLM via le function calling."""

import logging

from eva.config import Settings
from eva.tools.base import Tool, ToolRegistry
from eva.tools.clock import ClockTool
from eva.tools.hue.client import HueClient, HueError
from eva.tools.hue.tools import create_hue_tools

logger = logging.getLogger(__name__)


def default_tools(settings: Settings) -> ToolRegistry:
    """Registre des outils disponibles selon la configuration."""
    registry = ToolRegistry([ClockTool()])

    if settings.hue_bridge_ip and settings.hue_app_key:
        client = HueClient(settings.hue_bridge_ip, settings.hue_app_key.get_secret_value())
        try:
            for tool in create_hue_tools(client):
                registry.register(tool)
        except HueError as e:
            logger.warning("Lumières Hue indisponibles : %s", e)

    return registry


__all__ = ["ClockTool", "Tool", "ToolRegistry", "default_tools"]
