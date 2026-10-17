from typing import Any

import pytest
from pydantic import BaseModel, Field, ValidationError

from eva.domain import NoArgs, Tool, ToolEffect, choice, normalize, with_choices


class Args(BaseModel):
    target: str = Field(description="Cible.")
    level: int | None = Field(default=None, ge=1, le=100, description="Niveau.")
    color: str | None = Field(default=None, description="Couleur.")


class ArgsTool(Tool[Args]):
    name = "demo"
    description = "Démo."
    effect = ToolEffect.ACTION

    def __init__(self, targets: list[str]) -> None:
        self.args_model = with_choices(
            Args, target=choice(targets, aliases={"capitale": "Paris"}), color=choice(["rouge"])
        )

    async def run(self, args: Args) -> str:
        return args.target


def test_spec_schema_is_generated_and_simplified() -> None:
    spec = ArgsTool(["Lyon", "Paris"]).spec()

    assert spec.name == "demo"
    assert spec.effect is ToolEffect.ACTION
    assert spec.input_schema == {
        "type": "object",
        "properties": {
            "target": {"description": "Cible.", "enum": ["Lyon", "Paris"], "type": "string"},
            "level": {"type": "integer", "minimum": 1, "maximum": 100, "description": "Niveau."},
            "color": {"enum": ["rouge"], "type": "string", "description": "Couleur."},
        },
        "required": ["target"],
    }


def test_choices_tolerate_case_accents_and_aliases() -> None:
    tool = ArgsTool(["Lyon", "Paris"])

    assert tool.parse_args({"target": "LYON"}).target == "Lyon"
    assert tool.parse_args({"target": "capitale"}).target == "Paris"


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"target": "Nice"},
        {"target": "Lyon", "level": 0},
        {"target": "Lyon", "color": "x"},
    ],
)
def test_invalid_arguments_are_rejected(arguments: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ArgsTool(["Lyon"]).parse_args(arguments)


def test_no_args_schema_is_empty_object() -> None:
    class Ping(Tool[NoArgs]):
        name = "ping"
        description = "Ping."
        effect = ToolEffect.READ
        args_model = NoArgs

        async def run(self, args: NoArgs) -> str:
            return "pong"

    assert Ping().spec().input_schema == {"type": "object", "properties": {}}


def test_normalize() -> None:
    assert normalize("  Détente   Été ") == "detente ete"
