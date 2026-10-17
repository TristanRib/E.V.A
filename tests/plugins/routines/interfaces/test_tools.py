"""Outil `run_routine` : description, choix proposés au LLM, texte produit."""

import pytest
from pydantic import ValidationError

from eva.application import Toolbox
from eva.domain import ToolEffect
from eva.plugins.routines.application import RoutineRunner
from eva.plugins.routines.domain import Routine, Step
from eva.plugins.routines.interfaces.tools import RunRoutineTool
from fakes import EchoTool

ROUTINES = [
    Routine("Apocalypse", (Step("echo", {"value": 1}),), "tout en rouge"),
    Routine("Calme", (Step("echo", {"value": 2}), Step("echo", {"value": 3}))),
]


@pytest.fixture
def tool() -> RunRoutineTool:
    return RunRoutineTool(RoutineRunner(ROUTINES, Toolbox([EchoTool()])), ROUTINES)


def test_spec_lists_routines_with_descriptions(tool: RunRoutineTool) -> None:
    spec = tool.spec()

    assert spec.effect is ToolEffect.ACTION
    assert "Apocalypse (tout en rouge) ; Calme." in spec.description
    assert spec.input_schema["properties"]["routine"]["enum"] == ["Apocalypse", "Calme"]


def test_names_are_case_insensitive_and_closed(tool: RunRoutineTool) -> None:
    assert tool.parse_args({"routine": "APOCALYPSE"}).routine == "Apocalypse"
    with pytest.raises(ValidationError):
        tool.parse_args({"routine": "Sonar"})


async def test_run_summarizes_all_steps(tool: RunRoutineTool) -> None:
    result = await tool.run(tool.parse_args({"routine": "calme"}))

    assert result == "Routine « Calme » lancée : 2 3"
