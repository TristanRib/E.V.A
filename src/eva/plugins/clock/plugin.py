"""Plugin horloge : date et heure locales."""

from collections.abc import Sequence
from typing import Any

from eva.domain import Tool
from eva.plugins.base import NoConfig, Plugin, PluginContext
from eva.plugins.clock.interfaces.tools import ClockTool


class ClockPlugin(Plugin[NoConfig]):
    config_model = NoConfig

    async def setup(self, context: PluginContext[NoConfig]) -> Sequence[Tool[Any]]:
        return [ClockTool()]
