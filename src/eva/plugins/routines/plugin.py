"""Plugin routines : assemble les routines configurées et leur outil de lancement."""

from collections.abc import Sequence
from typing import Any

from eva.domain import Tool
from eva.plugins.base import Plugin, PluginContext, PluginUnavailable
from eva.plugins.routines.application import RoutineRunner
from eva.plugins.routines.config import RoutineConfig, RoutinesConfig
from eva.plugins.routines.domain import Routine, Step
from eva.plugins.routines.interfaces.tools import RUN_ROUTINE, RunRoutineTool


class RoutinesPlugin(Plugin[RoutinesConfig]):
    config_model = RoutinesConfig

    async def setup(self, context: PluginContext[RoutinesConfig]) -> Sequence[Tool[Any]]:
        if not context.config.routine:
            raise PluginUnavailable(
                "aucune routine définie ([[plugins.routines.routine]] dans eva.toml)"
            )

        routines = [_to_domain(config) for config in context.config.routine]
        runner = RoutineRunner(routines, context.tools, forbidden_tools={RUN_ROUTINE})
        return [RunRoutineTool(runner, routines)]


def _to_domain(config: RoutineConfig) -> Routine:
    return Routine(
        name=config.name,
        description=config.description,
        steps=tuple(Step(step.tool, dict(step.args)) for step in config.steps),
    )
