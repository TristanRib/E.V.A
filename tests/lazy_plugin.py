"""Plugin factice qui ne doit jamais être importé s'il n'est pas activé."""

from collections.abc import Sequence
from typing import Any

from eva.domain import Tool
from eva.plugins import NoConfig, Plugin, PluginContext


class LazyPlugin(Plugin[NoConfig]):
    config_model = NoConfig

    async def setup(self, context: PluginContext[NoConfig]) -> Sequence[Tool[Any]]:
        return []
