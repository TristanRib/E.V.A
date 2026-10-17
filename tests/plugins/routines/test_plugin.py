"""Assemblage du plugin routines depuis la configuration."""

from contextlib import AsyncExitStack

import pytest
from pydantic import ValidationError

from eva.application import Toolbox
from eva.config import Secrets
from eva.plugins import PluginContext, PluginUnavailable
from eva.plugins.routines import RoutinesPlugin
from eva.plugins.routines.config import RoutinesConfig
from fakes import EchoTool

APOCALYPSE = {
    "name": "Apocalypse",
    "description": "tout en rouge",
    "steps": [{"tool": "echo", "args": {"value": 1}}],
}


async def setup(config: RoutinesConfig) -> list[str]:
    async with AsyncExitStack() as resources:
        context = PluginContext(config, Secrets({}), resources, Toolbox([EchoTool()]))
        return [tool.name for tool in await RoutinesPlugin().setup(context)]


async def test_configured_routines_give_one_tool() -> None:
    assert await setup(RoutinesConfig.model_validate({"routine": [APOCALYPSE]})) == ["run_routine"]


async def test_no_routine_makes_plugin_unavailable() -> None:
    with pytest.raises(PluginUnavailable, match="aucune routine"):
        await setup(RoutinesConfig())


@pytest.mark.parametrize(
    "routines",
    [
        [APOCALYPSE, {**APOCALYPSE, "name": "apocalypse"}],
        [{**APOCALYPSE, "steps": []}],
    ],
)
def test_invalid_configurations_are_rejected(routines: list[dict[str, object]]) -> None:
    with pytest.raises(ValidationError):
        RoutinesConfig.model_validate({"routine": routines})
