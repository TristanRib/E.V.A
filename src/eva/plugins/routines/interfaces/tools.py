"""Outil de lancement des routines pour le LLM."""

from collections.abc import Sequence

from pydantic import BaseModel, Field

from eva.domain import Tool, ToolEffect, choice, with_choices
from eva.plugins.routines.application import RoutineRunner
from eva.plugins.routines.domain import Routine

RUN_ROUTINE = "run_routine"


class RoutineArgs(BaseModel):
    routine: str = Field(description="Routine à lancer.")


class RunRoutineTool(Tool[RoutineArgs]):
    name = RUN_ROUTINE
    effect = ToolEffect.ACTION

    def __init__(self, runner: RoutineRunner, routines: Sequence[Routine]) -> None:
        self._runner = runner
        self.description = (
            "Lance une routine : une suite d'actions prédéfinies, exécutées d'un coup. "
            "Routines disponibles : " + " ; ".join(_describe(r) for r in routines) + "."
        )
        self.args_model = with_choices(RoutineArgs, routine=choice(r.name for r in routines))

    async def run(self, args: RoutineArgs) -> str:
        routine, results = await self._runner.run(args.routine)
        return f"Routine « {routine.name} » lancée : " + " ".join(r.content for r in results)


def _describe(routine: Routine) -> str:
    return f"{routine.name} ({routine.description})" if routine.description else routine.name
