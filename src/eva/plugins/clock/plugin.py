"""Plugin horloge : date et heure locales."""

from collections.abc import Sequence
from contextlib import AsyncExitStack
from typing import Any

from eva.domain import Tool
from eva.plugins.clock.tools import ClockTool


class ClockPlugin:
    name = "clock"

    async def create_tools(self, resources: AsyncExitStack) -> Sequence[Tool[Any]]:
        return [ClockTool()]
