"""Lancement des routines : vérification complète avant exécution, puis étapes dans l'ordre."""

import pytest
from pydantic import BaseModel

from eva.application import Toolbox
from eva.domain import Tool, ToolEffect, ToolError
from eva.plugins.routines.application import RoutineRunner
from eva.plugins.routines.domain import Routine, RoutineError, Step


class PaintArgs(BaseModel):
    target: str
    color: str


class PaintTool(Tool[PaintArgs]):
    name = "paint"
    description = "Peint une cible."
    effect = ToolEffect.ACTION
    args_model = PaintArgs

    def __init__(self) -> None:
        self.applied: list[tuple[str, str]] = []

    async def run(self, args: PaintArgs) -> str:
        if args.color == "panne":
            raise ToolError("Service injoignable.")
        self.applied.append((args.target, args.color))
        return f"{args.target} : {args.color}."


def paint(target: str, color: str) -> Step:
    return Step("paint", {"target": target, "color": color})


@pytest.fixture
def tool() -> PaintTool:
    return PaintTool()


def runner_for(tool: PaintTool, *routines: Routine) -> RoutineRunner:
    return RoutineRunner(routines, Toolbox([tool]), forbidden_tools={"run_routine"})


async def test_steps_run_in_order(tool: PaintTool) -> None:
    runner = runner_for(tool, Routine("Alerte", (paint("A", "rouge"), paint("B", "bleu"))))

    routine, results = await runner.run("alerte")

    assert routine.name == "Alerte"
    assert tool.applied == [("A", "rouge"), ("B", "bleu")]
    assert [r.content for r in results] == ["A : rouge.", "B : bleu."]


async def test_invalid_step_prevents_any_action(tool: PaintTool) -> None:
    routine = Routine(
        "Cassé", (paint("A", "rouge"), Step("paint", {"target": "B"}), Step("inconnu"))
    )

    with pytest.raises(RoutineError, match="rien n'a été modifié") as error:
        await runner_for(tool, routine).run("Cassé")

    assert "étape 2 (paint)" in str(error.value)
    assert "étape 3 (inconnu)" in str(error.value)
    assert tool.applied == []


async def test_routine_cannot_run_a_routine(tool: PaintTool) -> None:
    routine = Routine("Boucle", (Step("run_routine", {"routine": "Boucle"}),))

    with pytest.raises(RoutineError, match="outil interdit"):
        await runner_for(tool, routine).run("Boucle")


async def test_failing_step_stops_and_reports_progress(tool: PaintTool) -> None:
    routine = Routine("Partiel", (paint("A", "rouge"), paint("B", "panne"), paint("C", "vert")))

    with pytest.raises(RoutineError, match=r"étape 2/3 \(paint\) : Service injoignable"):
        await runner_for(tool, routine).run("Partiel")

    assert tool.applied == [("A", "rouge")]


async def test_unknown_routine_lists_available_ones(tool: PaintTool) -> None:
    with pytest.raises(RoutineError, match="Routines : Alerte"):
        await runner_for(tool, Routine("Alerte", (paint("A", "rouge"),))).run("Calme")
